"""Main PLUX device interface and data acquisition."""

from __future__ import annotations

import logging
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

from mobi_physio_api.platform_detection import setup_plux_import_path
from mobi_physio_api.sensor_detection import get_sensor_info
from mobi_physio_api.streaming import LSLStreamer

logger = logging.getLogger(__name__)


def _format_mac_address(mac_address: str) -> str:
    """Format MAC address for the current platform.
    
    Args:
        mac_address: MAC address in standard format (e.g., 00:07:80:8C:08:DF)
        
    Returns:
        Platform-specific MAC address format
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows uses BTH prefix
        if not mac_address.startswith("BTH"):
            return f"BTH{mac_address}"
        return mac_address
    
    # macOS/Linux use dash-separated format
    if ":" in mac_address:
        return mac_address.replace(":", "-")
    return mac_address


class PluxDevice:
    """PLUX biosignals device interface with auto-detection and LSL streaming."""
    
    def __init__(
        self,
        mac_address: str,
        sampling_rate: float = 1000.0,
        stream_name: str = "biosignalsplux",
        plux_sdk_path: Path | None = None,
        connection_timeout: int = 60,
    ) -> None:
        """Initialize PLUX device.
        
        Args:
            mac_address: Device MAC address (format varies by OS).
            sampling_rate: Sampling rate in Hz.
            stream_name: Name for LSL stream.
            plux_sdk_path: Base path to PLUX SDK. Defaults to current directory.
            connection_timeout: Connection timeout in seconds.
            
        Raises:
            RuntimeError: If PLUX SDK cannot be loaded.
        """
        self.mac_address = _format_mac_address(mac_address)
        self.sampling_rate = sampling_rate
        self.stream_name = stream_name
        self.connection_timeout = connection_timeout
        
        # Set up PLUX SDK import path
        if plux_sdk_path is None:
            plux_sdk_path = Path.cwd()
        
        self.plux_path = setup_plux_import_path(plux_sdk_path)
        
        # Import PLUX after setting up path
        try:
            import plux  # type: ignore[import-untyped]
            self.plux = plux
        except ImportError as e:
            msg = f"Failed to import PLUX library from {self.plux_path}: {e}"
            raise RuntimeError(msg) from e
        
        # Device state
        self.device: Any | None = None
        self.channels: list[int] = []
        self.sensor_types: dict[int, str] = {}
        self.sensor_info: dict[int, dict[str, Any]] = {}
        self.sources: list[Any] = []
        self.running = False
        
        # Streaming
        self.streamer = LSLStreamer(
            stream_name=stream_name,
            sampling_rate=sampling_rate,
        )
        
        # Statistics
        self.sample_count = 0
        self.last_print_time = time.time()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def discover_sensors(self) -> dict[int, str]:
        """Auto-detect connected sensors and their types.
        
        Returns:
            Dictionary mapping port numbers to sensor types.
            
        Raises:
            RuntimeError: If device connection fails or no sensors found.
        """
        if self.device is None:
            self._connect_device()
        
        # Use the new sensor detection function
        channels, sensor_types, sensor_info, sources = get_sensor_info(self.device)
        
        self.channels = channels
        self.sensor_types = sensor_types
        self.sensor_info = sensor_info
        self.sources = sources
        
        if not self.channels:
            msg = "No sensors detected on device"
            raise RuntimeError(msg)
        
        logger.info("Detected sensors: %s", self.sensor_types)
        return self.sensor_types
    
    def setup_streaming(self) -> None:
        """Set up LSL streaming with detected channels."""
        if not self.channels:
            msg = "No channels configured. Call discover_sensors() first."
            raise RuntimeError(msg)
        
        self.streamer.setup_channels(self.sensor_types, self.channels)
        self.streamer.create_stream()
        
        logger.info(
            "LSL stream created with %d channels",
            self.streamer.get_channel_count(),
        )
        for name in self.streamer.get_channel_names():
            logger.debug("  - %s", name)
    
    def start_acquisition(self, debug_interval: int = 1000) -> None:
        """Start data acquisition and streaming.
        
        Args:
            debug_interval: Print debug info every N samples.
        """
        if not self.channels:
            msg = "No channels configured. Call discover_sensors() first."
            raise RuntimeError(msg)
        
        if self.streamer.outlet is None:
            msg = "Streaming not set up. Call setup_streaming() first."
            raise RuntimeError(msg)
        
        logger.info("Starting acquisition on ports: %s", self.channels)
        logger.info("Sensor types: %s", list(self.sensor_types.values()))
        logger.info("LSL channels: %s", self.streamer.get_channel_names())
        logger.info("Sampling rate: %s Hz", self.sampling_rate)
        logger.info("Device MAC: %s", self.mac_address)
        
        # Create device wrapper for callbacks
        device_wrapper = PluxDeviceWrapper(
            device=self.device,
            streamer=self.streamer,
            sensor_types=self.sensor_types,
            channels=self.channels,
            debug_interval=debug_interval,
        )
        
        logger.info("Starting device acquisition...")
        self.running = True
        device_wrapper.start(self.sampling_rate, self.sources)
        
        logger.info("Device started. Entering streaming loop...")
        logger.info("💡 Press Ctrl+C to stop, or press 'q' + Enter to quit...")
        
        # Start keyboard input thread
        input_thread = threading.Thread(target=self._check_keyboard_input, daemon=True)
        input_thread.start()
        
        # Enter acquisition loop
        device_wrapper.loop()
    
    def stop_acquisition(self) -> None:
        """Stop data acquisition and clean up."""
        logger.info("Stopping acquisition...")
        self.running = False
        
        if self.device:
            try:
                self.device.stop()
                self.device.close()
            except Exception as e:
                logger.warning("Warning during device stop: %s", e)
        
        self._cleanup_processes()
    
    def _connect_device(self) -> None:
        """Connect to the PLUX device with timeout and retry logic."""
        logger.info(
            "Connecting to device %s (timeout: %ds)...", 
            self.mac_address, 
            self.connection_timeout
        )
        
        start_time = time.time()
        retry_interval = 2.0  # Retry every 2 seconds
        last_error = None
        attempt_count = 0
        
        while time.time() - start_time < self.connection_timeout:
            attempt_count += 1
            try:
                logger.info(
                    "🔍 Connection attempt #%d (MAC: %s)...", 
                    attempt_count, 
                    self.mac_address
                )
                self.device = self.plux.SignalsDev(self.mac_address)
                logger.info("✅ Connected to device: %s", self.mac_address)
                return
            except Exception as e:
                last_error = e
                elapsed = time.time() - start_time
                remaining = self.connection_timeout - elapsed
                
                if remaining <= 2:  # Stop if less than 2 seconds remaining
                    break
                
                # Provide more helpful error messages
                error_msg = str(e)
                if "communication port could not be initialized" in error_msg.lower():
                    helpful_msg = "Device not found or not paired"
                elif "access denied" in error_msg.lower():
                    helpful_msg = "Permission denied - device may be in use"
                elif "failed bootstrap checkin" in error_msg.lower():
                    helpful_msg = "Bluetooth communication failed"
                elif ("bluetooth" in error_msg.lower() and 
                      "not found" in error_msg.lower()):
                    helpful_msg = "Bluetooth device not found"
                elif platform.system() == "Windows" and "com port" in error_msg.lower():
                    helpful_msg = "Windows COM port error - check Bluetooth pairing"
                else:
                    helpful_msg = error_msg
                
                logger.warning("❌ Attempt #%d failed: %s", attempt_count, helpful_msg)
                
                # Show progress
                if remaining > retry_interval:
                    logger.info(
                        "⏳ Retrying in %.1fs... (%.1fs remaining)",
                        retry_interval,
                        remaining
                    )
                    time.sleep(retry_interval)
                else:
                    logger.info("⏳ Final attempt in %.1fs...", remaining)
                    time.sleep(remaining)
        
        # If we get here, connection failed
        elapsed = time.time() - start_time
        
        # Try to provide a more helpful final error message
        if (last_error and 
            "communication port could not be initialized" in str(last_error).lower()):
            msg = (
                f"Device {self.mac_address} not found or not paired. "
                f"Check Bluetooth connection and ensure device is discoverable. "
                f"(Timeout: {self.connection_timeout}s)"
            )
        else:
            msg = (
                f"Failed to connect to device {self.mac_address} after "
                f"{elapsed:.1f} seconds (timeout: {self.connection_timeout}s)"
            )
        logger.error(msg)
        raise RuntimeError(msg)
    
    def _check_keyboard_input(self) -> None:
        """Check for keyboard input in a separate thread."""
        while self.running:
            try:
                user_input = input().strip().lower()
                if user_input == "q":
                    logger.info("🛑 'q' pressed - shutting down...")
                    self.running = False
                    break
            except (EOFError, KeyboardInterrupt):
                break
    
    def _signal_handler(self, sig: int, frame: FrameType | None) -> None:
        """Handle Ctrl+C gracefully."""
        logger.info("🛑 Shutdown requested (Ctrl+C detected)...")
        self.stop_acquisition()
        logger.info("👋 Goodbye!")
        sys.exit(0)
    
    def _cleanup_processes(self) -> None:
        """Clean up any stuck PLUX processes."""
        logger.info("🧹 Cleaning up PLUX processes...")
        try:
            if platform.system() == "Windows":
                # Windows process cleanup - try various possible process names
                processes_to_kill = [
                    "bth_macprocess.exe",
                    "plux.exe", 
                    "python.exe",  # Sometimes Python processes get stuck
                ]
                
                for process_name in processes_to_kill:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", process_name], 
                        check=False, 
                        capture_output=True,
                        timeout=5  # Don't hang if taskkill is slow
                    )
            else:
                # Unix/Linux/macOS process cleanup
                subprocess.run(["pkill", "-f", "bth_macprocess"], check=False)
                subprocess.run(["pkill", "-f", "plux"], check=False)
            
            logger.info("✓ Cleanup completed")
        except Exception as e:
            logger.warning("Cleanup warning: %s", e)


class PluxDeviceWrapper:
    """Wrapper class to handle PLUX device callbacks."""
    
    def __init__(
        self,
        device: Any,  # noqa: ANN401
        streamer: LSLStreamer,
        sensor_types: dict[int, str],
        channels: list[int],
        debug_interval: int = 1000,
    ) -> None:
        """Initialize device wrapper.
        
        Args:
            device: PLUX device instance.
            streamer: LSL streamer instance.
            sensor_types: Mapping of port to sensor type.
            channels: List of active channels.
            debug_interval: Debug print interval in samples.
        """
        self.device = device
        self.streamer = streamer
        self.sensor_types = sensor_types
        self.channels = channels
        self.debug_interval = debug_interval
        
        self.sample_count = 0
        self.last_print_time = time.time()
        self.running = True
        self.logger = logging.getLogger(f"{__name__}.PluxDeviceWrapper")
    
    def start(self, sampling_rate: float, sources: list[Any]) -> None:
        """Start the device acquisition."""
        self.device.start(sampling_rate, sources)
    
    def loop(self) -> None:
        """Enter the device acquisition loop."""
        # Monkey-patch the device's onRawFrame method
        original_method = getattr(self.device, "onRawFrame", None)
        self.device.onRawFrame = self.on_raw_frame
        
        try:
            self.device.loop()
        finally:
            # Restore original method if it existed
            if original_method:
                self.device.onRawFrame = original_method
    
    def on_raw_frame(self, sequence: int, data: list[float]) -> bool:
        """Handle incoming data frames.
        
        Args:
            sequence: Frame sequence number.
            data: Raw sensor data.
            
        Returns:
            False to continue acquisition, True to stop.
        """
        if not self.running:
            return True  # Stop the loop
        
        timestamp = time.time()
        self.sample_count += 1
        
        # Process data for LSL streaming
        processed_data = self.streamer.process_raw_data(
            data, self.sensor_types, self.channels
        )
        
        # Push to LSL stream
        self.streamer.push_sample(processed_data, timestamp)
        
        # Log debug information
        if self.sample_count % self.debug_interval == 0:
            elapsed = time.time() - self.last_print_time
            actual_rate = self.debug_interval / elapsed if elapsed > 0 else 0
            
            self.logger.debug("Sample #%d", self.sample_count)
            self.logger.debug("  Sequence: %s", sequence)
            self.logger.debug("  Raw Data: %s", data)
            self.logger.debug("  LSL Data: %s", processed_data)
            self.logger.debug("  Ports: %s", self.channels)
            self.logger.debug(
                "  Sensor types: %s",
                list(self.sensor_types.values()),
            )
            self.logger.debug("  LSL channels: %s", self.streamer.get_channel_names())
            self.logger.debug("  Actual rate: %.1f Hz", actual_rate)
            self.logger.debug("  Timestamp: %s", timestamp)
            self.logger.debug("-" * 50)
            
            self.last_print_time = time.time()
        
        return False  # Continue acquisition
