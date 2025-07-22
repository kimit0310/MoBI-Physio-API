""".. include:: ../../README.md"""  # noqa: D415

from mobi_physio_api.device import PluxDevice
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
]
