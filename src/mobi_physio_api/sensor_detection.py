"""Sensor detection and channel mapping for PLUX devices."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# PLUX sensor type mappings based on official documentation
SENSOR_TYPE_MAPPING = {
    0: "EMG",  # Electromyography
    1: "ECG",  # Electrocardiography
    2: "EDA",  # Electrodermal Activity (GSR)
    3: "EEG",  # Electroencephalography
    4: "ACC",  # Accelerometer
    5: "GYRO",  # Gyroscope
    6: "MAG",  # Magnetometer
    7: "RSP",  # Respiratory
    8: "PZT",  # Piezoelectric
    9: "TEMP",  # Temperature
    69: "SpO2",  # Pulse oximetry
    70: "PPG",  # Photoplethysmography
}

# Default channel names for different sensor types
DEFAULT_CHANNEL_NAMES = {
    "EMG": "EMG_CH{port}",
    "ECG": "ECG_CH{port}",
    "EDA": "EDA_CH{port}",
    "EEG": "EEG_CH{port}",
    "ACC": "ACC_CH{port}",
    "GYRO": "GYRO_CH{port}",
    "MAG": "MAG_CH{port}",
    "RSP": "RSP_CH{port}",
    "PZT": "PZT_CH{port}",
    "TEMP": "TEMP_CH{port}",
    "SpO2": "SpO2_CH{port}",
    "PPG": "PPG_CH{port}",
    "Unknown": "UNKNOWN_CH{port}",
}


def detect_sensor_type(sensor: Any, properties: dict[str, Any], port: int) -> str:  # noqa: ANN401
    """Automatically detect sensor type based on sensor properties and characteristics.

    Args:
        sensor: PLUX sensor object
        properties: Device properties dictionary
        port: Port number

    Returns:
        Detected sensor type string
    """
    # Known sensor type mappings from PLUX documentation
    type_map = SENSOR_TYPE_MAPPING

    # Get base sensor type from the type field
    base_type = type_map.get(sensor.type, f"Unknown_Type{sensor.type}")

    # For accelerometers, try to determine axis based on characteristics, port,
    # or other info
    if sensor.type == 4 or base_type == "ACC":
        characteristics = sensor.characteristics

        # Look for axis information in characteristics
        if isinstance(characteristics, dict):
            if "axis" in characteristics:
                axis = characteristics["axis"]
                return f"ACC_{axis}"
            if "channel" in characteristics:
                channel = characteristics["channel"]
                axis_map = {0: "X", 1: "Y", 2: "Z"}
                axis = axis_map.get(channel, channel)
                return f"ACC_{axis}"

        # Try to infer axis from port number (common convention: consecutive ports)
        # This is heuristic and may not always be accurate
        if port in [5, 6, 7]:  # Common accelerometer port arrangement
            axis_map = {5: "X", 6: "Y", 7: "Z"}
            return f"ACC_{axis_map[port]}"
        if port in [8, 9, 10]:  # Alternative arrangement
            axis_map = {8: "X", 9: "Y", 10: "Z"}
            return f"ACC_{axis_map[port]}"

        # If no axis info available, just return ACC
        return "ACC"

    # Special handling for digital sensors
    if sensor.type == 69:  # SpO2
        return "SpO2"

    # Try to enhance detection using productID or other properties
    product_id = "Unknown"
    if hasattr(sensor, "productID"):
        product_id = str(sensor.productID)
    elif isinstance(properties, dict) and "productID" in properties:
        product_id = str(properties["productID"])

    # Enhanced detection based on productID patterns (if available)
    if product_id != "Unknown":
        product_id_lower = product_id.lower()
        if "ecg" in product_id_lower or "electrocardiogram" in product_id_lower:
            return "ECG"
        if "emg" in product_id_lower or "electromyogram" in product_id_lower:
            return "EMG"
        if (
            "eda" in product_id_lower
            or "gsr" in product_id_lower
            or "galvanic" in product_id_lower
        ):
            return "EDA"
        if "spo2" in product_id_lower or "oximetry" in product_id_lower:
            return "SpO2"
        if "acc" in product_id_lower or "accelerometer" in product_id_lower:
            return "ACC"
        if "ppg" in product_id_lower or "photoplethysmography" in product_id_lower:
            return "PPG"
        if "resp" in product_id_lower or "respiratory" in product_id_lower:
            return "RSP"

    # For other sensors, use the base type from type mapping
    return base_type


def get_sensor_info(
    device: Any,
) -> tuple[  # noqa: ANN401
    list[int], dict[int, str], dict[int, dict[str, Any]], list[Any]
]:
    """Get sensor information and automatically detect channels.

    Args:
        device: PLUX device object

    Returns:
        Tuple of (channels, sensor_types, sensor_info, sources)
    """
    try:
        sensors = device.getSensors()
        logger.info(f"Auto-detected {len(sensors)} sensors")

        # Get device properties for additional sensor information
        try:
            properties = device.getProperties()
            logger.info(f"Device properties: {properties}")
        except Exception as e:
            logger.warning(f"Could not get device properties: {e}")
            properties = {}

        channels = []
        sensor_types = {}
        sensor_info = {}
        sources = []  # Store plux.Source objects for proper configuration

        # Import plux here to avoid circular imports
        try:
            import plux  # noqa: F401
        except ImportError:
            logger.error(
                "PLUX API not available. Cannot proceed with sensor detection."
            )
            raise

        for port, sensor in sensors.items():
            channels.append(port)

            # Log raw sensor information for debugging
            logger.info(f"Port {port}: RAW INFO")
            logger.info(f"  Type: {sensor.type}")
            logger.info(f"  Class: {sensor.clas}")
            logger.info(f"  Serial: {sensor.serialNum}")
            logger.info(f"  HW Version: {sensor.hwVersion}")
            logger.info(f"  Characteristics: {sensor.characteristics}")

            # Try to get productID from sensor or device properties
            product_id = "Unknown"
            if hasattr(sensor, "productID"):
                product_id = sensor.productID
            elif "productID" in properties:
                product_id = properties["productID"]
            logger.info(f"  Product ID: {product_id}")

            # Automatically detect sensor type based on actual sensor properties
            sensor_type = detect_sensor_type(sensor, properties, port)
            sensor_types[port] = sensor_type

            logger.info(f"  🎯 DETECTED TYPE: {sensor_type}")

            # Store detailed sensor info
            sensor_info[port] = {
                "type": sensor.type,
                "class": sensor.clas,
                "characteristics": sensor.characteristics,
                "serial": sensor.serialNum,
                "hw_version": sensor.hwVersion,
                "product_id": product_id,
            }

            # Create appropriate source configuration
            if sensor.type == 69:  # SpO2 sensor - Digital channel
                logger.info(
                    "  🔧 Configured as DIGITAL channel (SpO2 with RED/INFRARED)"
                )
                source = plux.Source()
                source.port = port
                source.freqDivisor = 1  # No subsampling
                source.nBits = 16  # 16-bit resolution
                source.chMask = 0x03  # Both RED and INFRARED derivations (binary 11)
                sources.append(source)
            else:  # Analog sensors (EMG, ECG, ACC, etc.)
                logger.info("  🔧 Configured as ANALOG channel")
                source = plux.Source()
                source.port = port
                source.freqDivisor = 1  # No subsampling
                source.nBits = 16  # 16-bit resolution
                sources.append(source)

        return channels, sensor_types, sensor_info, sources

    except Exception as e:
        logger.warning(f"Could not auto-detect sensors: {e}")
        logger.warning("Using fallback channels [1, 2, 3]")

        # Fallback sources
        fallback_sources = []

        # Import plux here to avoid circular imports
        try:
            import plux  # noqa: F401
        except ImportError:
            logger.error("PLUX API not available. Cannot create fallback sources.")
            raise

        for port in [1, 2, 3]:
            source = plux.Source()
            source.port = port
            source.freqDivisor = 1
            source.nBits = 16
            fallback_sources.append(source)

        return [1, 2, 3], {1: "RSP", 2: "EMG", 3: "EDA"}, {}, fallback_sources


def generate_channel_names(
    sensor_types: dict[int, str], sensor_info: dict[int, dict[str, Any]]
) -> dict[int, str]:
    """Generate appropriate channel names based on sensor types and information.

    Args:
        sensor_types: Dictionary mapping port to sensor type
        sensor_info: Dictionary mapping port to sensor information

    Returns:
        Dictionary mapping port to channel name
    """
    channel_names = {}

    for port, sensor_type in sensor_types.items():
        # Use the sensor type as the base name
        if sensor_type in DEFAULT_CHANNEL_NAMES:
            channel_names[port] = DEFAULT_CHANNEL_NAMES[sensor_type].format(port=port)
        else:
            # For custom sensor types (e.g., ACC_X), use the type directly
            channel_names[port] = f"{sensor_type}_CH{port}"

    return channel_names


def get_channel_mapping(device: Any) -> dict[str, int]:  # noqa: ANN401
    """Get channel mapping for the device.

    Args:
        device: PLUX device object

    Returns:
        Dictionary mapping channel names to port numbers
    """
    channels, sensor_types, sensor_info, sources = get_sensor_info(device)
    channel_names = generate_channel_names(sensor_types, sensor_info)

    # Create reverse mapping from channel names to ports
    channel_mapping = {}
    for port, channel_name in channel_names.items():
        channel_mapping[channel_name] = port

    return channel_mapping
