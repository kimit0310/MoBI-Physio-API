"""MoBI Physio API.

A robust, cross-platform Python API for PLUX biosignals devices (EMG, SpO2, 
EDA, ECG, ACC, etc.) with automatic sensor detection, LSL streaming, and 
production-ready features.

Features:
- Automatic sensor detection and configuration
- Multi-platform support (macOS, Windows, Linux)
- LSL streaming with proper channel naming
- Command-line interface for easy usage
- Type hints and modern Python practices

Example:
    >>> from mobi_physio_api import PluxDevice
    >>> device = PluxDevice(mac_address="00:07:80:8C:08:DF")
    >>> device.discover_sensors()
    >>> device.setup_streaming() 
    >>> device.start_acquisition()
"""

from mobi_physio_api.device import PluxDevice
from mobi_physio_api.platform_detection import setup_plux_import_path
from mobi_physio_api.sensor_detection import (
    SENSOR_TYPE_MAPPING,
    detect_sensor_type,
    generate_channel_names,
    get_channel_mapping,
    get_sensor_info,
)
from mobi_physio_api.streaming import LSLStreamer

__version__ = "0.1.0"
__author__ = "Child Mind Institute"
__email__ = "dair@childmind.org"

__all__ = [
    "PluxDevice",
    "SENSOR_TYPE_MAPPING",
    "detect_sensor_type",
    "get_sensor_info",
    "generate_channel_names",
    "get_channel_mapping",
    "LSLStreamer",
    "setup_plux_import_path",
]
