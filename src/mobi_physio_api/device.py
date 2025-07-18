"""Simplified PLUX device interface - core functionality only."""

from __future__ import annotations

import logging
import os
import platform
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

from pylsl import StreamInfo, StreamOutlet

logger = logging.getLogger(__name__)

# Global flag for emergency shutdown
_emergency_shutdown = threading.Event()


def setup_plux_import_path(base_path: Path) -> Path:
    """Set up PLUX SDK import path based on platform."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        machine = platform.machine()
        python_version = "".join(platform.python_version().split(".")[:2])
        
        if machine == "arm64":  # Apple Silicon
            for version in [python_version, "312", "311", "310", "39", "37"]:
                plux_path = base_path / "PLUX-API-Python3" / f"M1_{version}"
                if plux_path.exists():
                    sys.path.append(str(plux_path))
                    return plux_path
        else:  # Intel Mac
            for version in [python_version, "310", "39", "38", "37"]:
                plux_path = base_path / "PLUX-API-Python3" / "MacOS" / f"Intel{version}"
                if plux_path.exists():
                    sys.path.append(str(plux_path))
                    return plux_path
    elif system == "Linux":
        plux_path = base_path / "PLUX-API-Python3" / "Linux64"
        sys.path.append(str(plux_path))
        return plux_path
    elif system == "Windows":
        python_version = "".join(platform.python_version().split(".")[:2])
        arch = platform.architecture()[0][:2]
        plux_path = base_path / "PLUX-API-Python3" / f"Win{arch}_{python_version}"
        sys.path.append(str(plux_path))
        return plux_path
    
    raise RuntimeError(f"Unsupported platform: {system}")


def _format_mac_address(mac_address: str) -> str:
    """Format MAC address for the current platform."""
    if platform.system() == "Windows" and not mac_address.startswith("BTH"):
        return f"BTH{mac_address}"
    return mac_address  # Keep original format for macOS/Linux


class PluxDevice:
    """Simplified PLUX device with minimal, working functionality."""

    def __init__(
        self,
        mac_address: str,
        sampling_rate: float = 1000.0,
        stream_name: str = "biosignalsplux",
        plux_sdk_path: Path | None = None,
        manual_sensor_map: dict[int, str] | None = None,
    ) -> None:
        """Initialize PLUX device."""
        self.mac_address = _format_mac_address(mac_address)
        self.sampling_rate = sampling_rate
        self.stream_name = stream_name
        self.manual_sensor_map = manual_sensor_map or {}

        # Set up PLUX SDK
        if plux_sdk_path is None:
            plux_sdk_path = Path.cwd()
        
        self.plux_path = setup_plux_import_path(plux_sdk_path)

        # Import PLUX
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
        self.running = False

        # LSL stream
        self.outlet: StreamOutlet | None = None
        self.sample_count = 0
        self.last_print_time = time.time()

        # Signal handler
        signal.signal(signal.SIGINT, self._signal_handler)

    def connect_and_setup(self) -> None:
        """Connect to device and set up streaming."""
        logger.info("Connecting to device %s...", self.mac_address)
        
        # Create device instance using the working pattern from minimal_streaming.py
        self.device = self._create_working_device()
        
        # Detect sensors
        self._detect_sensors()
        
        # Create LSL stream
        self._setup_lsl_stream()

    def _create_working_device(self) -> Any:
        """Create PLUX device instance using the working pattern."""
        
        class WorkingDevice(self.plux.SignalsDev):
            def __init__(device_self, mac: str) -> None:
                # Don't call parent __init__ - this is the key insight!
                device_self.mac = mac
                device_self.parent_plux = self
                device_self.sample_count = 0
                device_self.last_print = time.time()
            
            def onRawFrame(device_self, seq: int, data: list[float]) -> bool:
                """Handle incoming data frames."""
                if not self.running or _emergency_shutdown.is_set():
                    return True  # Stop
                
                # Push data to LSL
                if self.outlet:
                    self.outlet.push_sample(data[:len(self.channels)])
                    device_self.sample_count += 1
                    
                    # Progress info and sample data every 1000 samples
                    if device_self.sample_count % 1000 == 0:
                        elapsed = time.time() - device_self.last_print
                        rate = 1000 / elapsed if elapsed > 0 else 0
                        
                        # Show actual sample data
                        sample_data = data[:len(self.channels)]
                        logger.info(
                            "Streaming: %d samples, %.1f Hz - Sample data: %s", 
                            device_self.sample_count, 
                            rate,
                            [f"{val:.2f}" for val in sample_data]
                        )
                        device_self.last_print = time.time()
                
                return False  # Continue
                
                return False  # Continue
        
        return WorkingDevice(self.mac_address)

    def _detect_sensors(self) -> None:
        """Detect connected sensors."""
        try:
            sensors = self.device.getSensors()
            logger.info("Found %d sensors", len(sensors))
            
            if not sensors:
                logger.warning("No sensors found, using common sensor layout")
                # Common PLUX sensor layout: EDA on port 1, EMG on port 2
                self.channels = [1, 2]
                self.sensor_types = {1: "EDA", 2: "EMG"}
                return
            
            # Sensor type mapping based on PLUX documentation
            type_map = {
                0: "EMG",    # Electromyography
                1: "ECG",    # Electrocardiography  
                2: "EDA",    # Electrodermal Activity (GSR)
                3: "EEG",    # Electroencephalography
                4: "ACC",    # Accelerometer
                7: "RSP",    # Respiratory
                69: "SpO2",  # Pulse oximetry
                70: "PPG",   # Photoplethysmography
            }
            
            self.channels = list(sensors.keys())
            self.sensor_types = {}
            
            # First pass: detect all sensors and show raw data
            logger.info("=== RAW SENSOR DETECTION ===")
            for port, sensor in sensors.items():
                logger.info("Port %d: raw_type=%d", port, sensor.type)
                try:
                    if hasattr(sensor, 'characteristics'):
                        logger.info("  Characteristics: %s", sensor.characteristics)
                    if hasattr(sensor, 'productID'):
                        logger.info("  ProductID: %s", sensor.productID)
                    if hasattr(sensor, 'description'):
                        logger.info("  Description: %s", sensor.description)
                except Exception as e:
                    logger.debug("  Error reading sensor details: %s", e)
            
            # Second pass: map sensor types
            logger.info("=== SENSOR TYPE MAPPING ===")
            for port, sensor in sensors.items():
                sensor_type = type_map.get(sensor.type, f"Unknown_Type{sensor.type}")
                self.sensor_types[port] = sensor_type
                logger.info("Port %d: %s (raw_type=%d)", port, sensor_type, sensor.type)
            
            # Try intelligent detection based on sensor characteristics
            logger.info("=== INTELLIGENT SENSOR DETECTION ===")
            self._detect_sensors_by_characteristics(sensors)
            
            # Apply any manual overrides if provided
            if hasattr(self, 'manual_sensor_map') and self.manual_sensor_map:
                logger.info("=== APPLYING MANUAL SENSOR OVERRIDES ===")
                for port, sensor_type in self.manual_sensor_map.items():
                    if port in self.sensor_types:
                        old_type = self.sensor_types[port]
                        self.sensor_types[port] = sensor_type
                        logger.info(
                            "Manual override: Port %d: %s -> %s", 
                            port, old_type, sensor_type
                        )
                
        except Exception as e:
            logger.warning("Sensor detection failed: %s", e)
            # Common PLUX sensor layout: EDA on port 1, EMG on port 2
            self.channels = [1, 2]
            self.sensor_types = {1: "EDA", 2: "EMG"}

    def _detect_sensors_by_characteristics(self, sensors: dict) -> None:
        """Detect sensor types based on their characteristics."""
        for port, sensor in sensors.items():
            detected_type = "EMG"  # Default fallback
            
            try:
                # Check if this is SpO2 first (different detection method)
                if sensor.type == 69:  # SpO2 sensor type
                    detected_type = "SpO2"
                    logger.info("Port %d: Detected SpO2 (sensor_type=69)", port)
                
                # Get sensor characteristics for analog sensors
                elif hasattr(sensor, 'characteristics') and sensor.characteristics:
                    chars = sensor.characteristics
                    
                    # EDA detection: typically has current source (iGain)
                    if 'iGain' in chars and chars.get('iGain', 0) > 100:
                        detected_type = "EDA"
                        logger.info("Port %d: Detected EDA (iGain=%s)", port, chars.get('iGain'))
                    
                    # RSP detection: low gain + low frequency (respiration belt characteristics)
                    elif ('vGain' in chars and chars.get('vGain', 0) <= 10 and
                          'lpFreq' in chars and chars.get('lpFreq', 0) <= 5):
                        detected_type = "RSP"  
                        logger.info("Port %d: Detected RSP (vGain=%s, lpFreq=%s)", 
                                  port, chars.get('vGain'), chars.get('lpFreq'))
                    
                    # ECG detection: high gain and moderate frequency
                    elif ('vGain' in chars and chars.get('vGain', 0) > 500 and
                          'lpFreq' in chars and chars.get('lpFreq', 0) < 200):
                        detected_type = "ECG"
                        logger.info("Port %d: Detected ECG (vGain=%s, lpFreq=%s)", 
                                  port, chars.get('vGain'), chars.get('lpFreq'))
                    
                    # EMG detection: high gain and high frequency
                    elif ('vGain' in chars and chars.get('vGain', 0) > 500 and
                          'lpFreq' in chars and chars.get('lpFreq', 0) > 400):
                        detected_type = "EMG"
                        logger.info("Port %d: Detected EMG (vGain=%s, lpFreq=%s)", 
                                  port, chars.get('vGain'), chars.get('lpFreq'))
                    
                    else:
                        logger.info("Port %d: Could not auto-detect, defaulting to EMG (chars=%s)", 
                                  port, chars)
                
                self.sensor_types[port] = detected_type
                
            except Exception as e:
                logger.warning("Error detecting sensor on port %d: %s", port, e)
                self.sensor_types[port] = "EMG"  # Safe fallback

    def _setup_lsl_stream(self) -> None:
        """Set up LSL stream."""
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
        """Start data acquisition and streaming."""
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
        """Stop streaming and cleanup."""
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

    def _signal_handler(self, sig: int, frame: FrameType | None) -> None:
        """Handle Ctrl+C gracefully with immediate shutdown."""
        logger.info("Interrupt received (Ctrl+C), shutting down immediately...")
        
        # Set global emergency flag
        _emergency_shutdown.set()
        
        # Set running to False to stop callbacks
        self.running = False
        
        # Force exit immediately without complex cleanup
        # The PLUX SDK can be unstable during interruption
        logger.info("Shutdown initiated. Exiting...")
        os._exit(0)
