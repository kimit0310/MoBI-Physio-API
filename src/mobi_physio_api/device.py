"""Simplified PLUX device interface - core functionality only."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pylsl import StreamInfo, StreamOutlet

from mobi_physio_api.platform_detection import setup_plux_import_path
from mobi_physio_api.sensor_detection import get_sensor_info
from mobi_physio_api.utils import format_mac_address, is_emergency_shutdown

logger = logging.getLogger(__name__)


class PluxDevice:
    """PLUX biosignals device interface for data streaming.

    Provides simplified interface for connecting to PLUX devices, detecting
    sensors automatically, and streaming data via Lab Streaming Layer (LSL).
    """

    def __init__(
        self,
        mac_address: str,
        sampling_rate: float = 1000.0,
        stream_name: str = "biosignalsplux",
        plux_sdk_path: Path | None = None,
        manual_sensor_map: dict[int, str] | None = None,
    ) -> None:
        """Initialize PLUX device interface.

        Args:
            mac_address: Device MAC address in format XX:XX:XX:XX:XX:XX.
            sampling_rate: Data acquisition frequency in Hz.
            stream_name: LSL stream identifier.
            plux_sdk_path: Path to PLUX SDK directory.
            manual_sensor_map: Override automatic sensor detection.
        """
        self.mac_address = format_mac_address(mac_address)
        self.sampling_rate = sampling_rate
        self.stream_name = stream_name
        self.manual_sensor_map = manual_sensor_map or {}

        # Set up PLUX SDK
        if plux_sdk_path is None:
            plux_sdk_path = Path.cwd()

        self.plux_path = setup_plux_import_path(plux_sdk_path)

        # Import PLUX
        try:
            import plux

            self.plux = plux
        except ImportError as e:
            msg = f"Failed to import PLUX library from {self.plux_path}: {e}"
            raise RuntimeError(msg) from e

        # Device state
        self.device: Any | None = None
        self.channels: list[int] = []
        self.sensor_types: dict[int, str] = {}
        self.running = False

        # LSL stream
        self.outlet: StreamOutlet | None = None
        self.sample_count = 0
        self.last_print_time = time.time()

        # Signal handler will be set up externally
        self.running = False

    def connect_and_setup(self) -> None:
        """Connect to device and configure sensors for streaming."""
        logger.info("Connecting to device %s...", self.mac_address)

        try:
            # Create device instance using the working pattern
            self.device = self._create_working_device()
            logger.info("Device connection established")

            # Wait a moment for connection to stabilize
            time.sleep(0.5)

            # Detect sensors
            logger.info("Detecting sensors...")
            self._detect_sensors()

            # Create LSL stream
            logger.info("Setting up LSL stream...")
            self._setup_lsl_stream()

            logger.info("Device setup complete")

        except Exception as e:
            logger.error("Failed to connect to device: %s", e)
            logger.error("Make sure the device is turned on and in pairing mode")
            logger.error("You may need to pair the device in Bluetooth settings first")
            raise

    def _create_working_device(self) -> Any:  # noqa: ANN401
        """Create PLUX device instance with proper initialization pattern.

        Returns:
            Configured PLUX device instance ready for data acquisition.
        """

        class WorkingDevice(self.plux.SignalsDev):  # type: ignore[misc,name-defined]
            def __init__(device_self, mac: str) -> None:
                # Call parent __init__ with the MAC address for proper connection
                super().__init__(mac)
                device_self.mac = mac
                device_self.parent_plux = self
                device_self.sample_count = 0
                device_self.last_print = time.time()

            def onRawFrame(device_self, seq: int, data: list[float]) -> bool:
                """Handle incoming data frames from PLUX device.

                Args:
                    seq: Frame sequence number.
                    data: Raw sensor data values.

                Returns:
                    True to stop acquisition, False to continue.
                """
                if not self.running or is_emergency_shutdown():
                    return True  # Stop

                # Push data to LSL
                if self.outlet:
                    self.outlet.push_sample(data[: len(self.channels)])
                    device_self.sample_count += 1

                    # Progress info and sample data every 1000 samples
                    if device_self.sample_count % 1000 == 0:
                        elapsed = time.time() - device_self.last_print
                        rate = 1000 / elapsed if elapsed > 0 else 0

                        # Show actual sample data
                        sample_data = data[: len(self.channels)]
                        logger.info(
                            "Streaming: %d samples, %.1f Hz - Sample data: %s",
                            device_self.sample_count,
                            rate,
                            [f"{val:.2f}" for val in sample_data],
                        )
                        device_self.last_print = time.time()

                return False  # Continue

        return WorkingDevice(self.mac_address)

    def _detect_sensors(self) -> None:
        """Detect connected sensors using automatic detection system."""
        try:
            channels, sensor_types, sensor_info, sources = get_sensor_info(self.device)
            self.channels = channels
            self.sensor_types = sensor_types
            logger.info("Found %d sensors", len(sensor_types))
            for port, sensor_type in sensor_types.items():
                logger.info("Port %d: %s", port, sensor_type)

            # Apply any manual overrides if provided
            if hasattr(self, "manual_sensor_map") and self.manual_sensor_map:
                logger.info("=== APPLYING MANUAL SENSOR OVERRIDES ===")
                for port, sensor_type in self.manual_sensor_map.items():
                    if port in self.sensor_types:
                        old_type = self.sensor_types[port]
                        self.sensor_types[port] = sensor_type
                        logger.info(
                            "Manual override: Port %d: %s -> %s",
                            port,
                            old_type,
                            sensor_type,
                        )

        except Exception as e:
            logger.warning("Sensor detection failed: %s", e)
            # Common PLUX sensor layout: EDA on port 1, EMG on port 2
            self.channels = [1, 2]
            self.sensor_types = {1: "EDA", 2: "EMG"}

    def _setup_lsl_stream(self) -> None:
        """Configure Lab Streaming Layer outlet for data transmission."""
        channel_names = [
            f"{self.sensor_types[port]}_CH{port}" for port in self.channels
        ]
        logger.info("Creating LSL stream with channels: %s", channel_names)

        info = StreamInfo(
            name=self.stream_name,
            type="Physiological",
            channel_count=len(channel_names),
            nominal_srate=self.sampling_rate,
            channel_format="float32",
            source_id=self.stream_name,
        )

        self.outlet = StreamOutlet(info)

    def start_streaming(self) -> None:
        """Start data acquisition and streaming to LSL outlet."""
        if not self.device or not self.outlet:
            msg = "Device not connected or stream not set up"
            raise RuntimeError(msg)

        logger.info("Starting acquisition on channels: %s", self.channels)
        logger.info("Sensor types: %s", list(self.sensor_types.values()))
        logger.info("Press Ctrl+C to stop...")

        # Create sources
        sources = []
        for port in self.channels:
            source = self.plux.Source()
            source.port = port
            source.freqDivisor = 1
            source.nBits = 16
            sources.append(source)

        # Start acquisition - the onRawFrame is already defined in WorkingDevice
        self.running = True

        try:
            self.device.start(self.sampling_rate, sources)

            # Use the working loop pattern from minimal_streaming.py
            logger.info("Starting data acquisition loop...")
            self.device.loop()  # This calls onRawFrame callbacks

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error("Error during streaming: %s", e)
        finally:
            logger.info("Cleaning up...")
            self.stop_streaming()

    def stop_streaming(self) -> None:
        """Stop data acquisition and clean up resources."""
        if not self.running:
            return  # Already stopped

        logger.info("Stopping acquisition...")
        self.running = False

        if self.device:
            try:
                # Give it a moment to finish current operations
                time.sleep(0.1)
                self.device.stop()
                logger.info("Device stopped successfully")
            except Exception as e:
                logger.warning("Warning during device stop: %s", e)

            try:
                self.device.close()
                logger.info("Device closed successfully")
            except Exception as e:
                logger.warning("Warning during device close: %s", e)

        # Clean up LSL outlet
        if self.outlet:
            try:
                del self.outlet
                self.outlet = None
                logger.info("LSL outlet cleaned up")
            except Exception as e:
                logger.warning("Warning during LSL cleanup: %s", e)
