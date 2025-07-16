"""Tests for sensor detection functionality."""

from unittest.mock import Mock

from mobi_physio_api.sensor_detection import (
    SENSOR_TYPE_MAPPING,
    detect_sensor_type,
    generate_channel_names,
)


class TestSensorDetection:
    """Test sensor detection functions."""

    def test_sensor_type_mapping(self) -> None:
        """Test sensor type mapping constants."""
        assert SENSOR_TYPE_MAPPING[0] == "EMG"
        assert SENSOR_TYPE_MAPPING[1] == "ECG"
        assert SENSOR_TYPE_MAPPING[2] == "EDA"
        assert SENSOR_TYPE_MAPPING[69] == "SpO2"

    def test_detect_sensor_type_basic(self) -> None:
        """Test basic sensor type detection."""
        # Mock sensor object
        sensor = Mock()
        sensor.type = 69  # SpO2
        sensor.characteristics = {}

        properties = {}
        result = detect_sensor_type(sensor, properties, 1)

        assert result == "SpO2"

    def test_detect_sensor_type_emg(self) -> None:
        """Test EMG sensor detection."""
        sensor = Mock()
        sensor.type = 0  # EMG
        sensor.characteristics = {}

        properties = {}
        result = detect_sensor_type(sensor, properties, 1)

        assert result == "EMG"

    def test_detect_sensor_type_ecg(self) -> None:
        """Test ECG sensor detection."""
        sensor = Mock()
        sensor.type = 1  # ECG
        sensor.characteristics = {}

        properties = {}
        result = detect_sensor_type(sensor, properties, 2)

        assert result == "ECG"

    def test_detect_sensor_type_accelerometer(self) -> None:
        """Test accelerometer sensor detection with axis."""
        sensor = Mock()
        sensor.type = 4  # ACC
        sensor.characteristics = {"axis": "X"}

        properties = {}
        result = detect_sensor_type(sensor, properties, 5)

        assert result == "ACC_X"

    def test_detect_sensor_type_accelerometer_by_port(self) -> None:
        """Test accelerometer sensor detection by port inference."""
        sensor = Mock()
        sensor.type = 4  # ACC
        sensor.characteristics = {}

        properties = {}
        result = detect_sensor_type(sensor, properties, 6)  # Port 6 = Y axis

        assert result == "ACC_Y"

    def test_detect_sensor_type_unknown(self) -> None:
        """Test unknown sensor type."""
        sensor = Mock()
        sensor.type = 999  # Unknown type
        sensor.characteristics = {}

        properties = {}
        result = detect_sensor_type(sensor, properties, 1)

        assert result == "Unknown_Type999"

    def test_generate_channel_names(self) -> None:
        """Test channel name generation."""
        sensor_types = {1: "EMG", 2: "ECG", 3: "SpO2"}
        sensor_info = {1: {}, 2: {}, 3: {}}

        result = generate_channel_names(sensor_types, sensor_info)

        assert result[1] == "EMG_CH1"
        assert result[2] == "ECG_CH2"
        assert result[3] == "SpO2_CH3"

    def test_generate_channel_names_custom_type(self) -> None:
        """Test channel name generation with custom sensor type."""
        sensor_types = {1: "ACC_X", 2: "ACC_Y"}
        sensor_info = {1: {}, 2: {}}

        result = generate_channel_names(sensor_types, sensor_info)

        assert result[1] == "ACC_X_CH1"
        assert result[2] == "ACC_Y_CH2"
