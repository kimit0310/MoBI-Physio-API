"""Tests for LSL streaming functionality."""

from unittest.mock import Mock, patch

from mobi_physio_api.streaming import LSLStreamer


class TestLSLStreamer:
    """Test LSL streaming functionality."""

    def test_init(self) -> None:
        """Test LSLStreamer initialization."""
        streamer = LSLStreamer("test_stream", sampling_rate=1000.0)
        assert streamer.stream_name == "test_stream"
        assert streamer.sampling_rate == 1000.0
        assert streamer.channels == []
        assert streamer.channel_names == []
        assert streamer.outlet is None

    def test_setup_channels_single_sensor(self) -> None:
        """Test channel setup with single sensor."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        sensor_types = {1: "EMG"}
        channels = [1]

        streamer.setup_channels(sensor_types, channels)

        assert len(streamer.channels) == 1
        assert len(streamer.channel_names) == 1
        assert streamer.channel_names[0] == "EMG_1"

    def test_setup_channels_multiple_sensors(self) -> None:
        """Test channel setup with multiple sensors."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        sensor_types = {
            1: "EMG",
            2: "EDA",
            3: "RSP",
        }
        channels = [1, 2, 3]

        streamer.setup_channels(sensor_types, channels)

        assert len(streamer.channels) == 3
        assert len(streamer.channel_names) == 3
        assert "EMG_1" in streamer.channel_names
        assert "EDA_2" in streamer.channel_names
        assert "RSP_3" in streamer.channel_names

    def test_setup_channels_spo2_sensor(self) -> None:
        """Test channel setup with SpO2 sensor (dual channel)."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        sensor_types = {1: "SpO2"}
        channels = [1]

        streamer.setup_channels(sensor_types, channels)

        assert len(streamer.channels) == 2  # SpO2 has 2 channels
        assert len(streamer.channel_names) == 2
        assert "SpO2_1_RED" in streamer.channel_names
        assert "SpO2_1_INFRARED" in streamer.channel_names

    def test_setup_channels_acc_sensor(self) -> None:
        """Test channel setup with ACC sensor (triple channel)."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        sensor_types = {1: "ACC"}
        channels = [1]

        streamer.setup_channels(sensor_types, channels)

        assert len(streamer.channels) == 3  # ACC has 3 channels (X, Y, Z)
        assert len(streamer.channel_names) == 3
        assert "ACC_1_X" in streamer.channel_names
        assert "ACC_1_Y" in streamer.channel_names
        assert "ACC_1_Z" in streamer.channel_names

    @patch("mobi_physio_api.streaming.StreamInfo")
    @patch("mobi_physio_api.streaming.StreamOutlet")
    def test_create_stream(self, mock_outlet: Mock, mock_stream_info: Mock) -> None:
        """Test LSL stream creation."""
        # Mock pylsl components
        mock_info_instance = Mock()
        mock_outlet_instance = Mock()
        mock_stream_info.return_value = mock_info_instance
        mock_outlet.return_value = mock_outlet_instance

        streamer = LSLStreamer("test", sampling_rate=1000.0)
        streamer.channels = [1, 2]
        streamer.channel_names = ["EMG_1", "EDA_2"]
        streamer.channel_types = ["EMG", "EDA"]

        streamer.create_stream()

        # Should create StreamInfo with correct parameters
        mock_stream_info.assert_called_once()
        call_args = mock_stream_info.call_args
        # Verify the parameters are passed correctly
        assert call_args.kwargs["name"] == "test"
        assert call_args.kwargs["type"] == "Physiological"
        assert call_args.kwargs["channel_count"] == 2
        assert call_args.kwargs["nominal_srate"] == 1000.0
        assert call_args.kwargs["channel_format"] == "float32"
        assert call_args.kwargs["source_id"] == "biosignalsplux"

        # Should create StreamOutlet
        mock_outlet.assert_called_once_with(mock_info_instance)
        assert streamer.outlet == mock_outlet_instance

    def test_get_channel_count(self) -> None:
        """Test channel count getter."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        streamer.channels = [1, 2, 3]
        streamer.channel_names = ["EMG_1", "EDA_2", "ECG_3"]  # Match channels
        assert streamer.get_channel_count() == 3

    def test_get_channel_names(self) -> None:
        """Test channel names getter."""
        streamer = LSLStreamer("test", sampling_rate=1000.0)
        streamer.channel_names = ["EMG_1", "EDA_2"]
        assert streamer.get_channel_names() == ["EMG_1", "EDA_2"]

    def test_process_raw_data_single_channel(self) -> None:
        """Test raw data processing for single channel sensors."""
        streamer = LSLStreamer("test", 1000.0)
        sensor_types = {1: "EMG"}
        channels = [1]

        raw_data = [123.45]
        processed = streamer.process_raw_data(raw_data, sensor_types, channels)

        assert processed == [123.45]

    def test_process_raw_data_spo2(self) -> None:
        """Test raw data processing for SpO2 sensor."""
        streamer = LSLStreamer("test", 1000.0)
        sensor_types = {1: "SpO2"}
        channels = [1]

        # SpO2 data: [RED, INFRARED]
        raw_data = [12345]  # Packed 16-bit values
        processed = streamer.process_raw_data(raw_data, sensor_types, channels)

        # Should unpack into 2 channels
        assert len(processed) == 2

    def test_process_raw_data_acc(self) -> None:
        """Test raw data processing for ACC sensor."""
        streamer = LSLStreamer("test", 1000.0)
        sensor_types = {1: "ACC"}
        channels = [1]

        # ACC data: single value representing 3-axis data
        raw_data = [123456]
        processed = streamer.process_raw_data(raw_data, sensor_types, channels)

        # Should unpack into 3 channels (X, Y, Z)
        assert len(processed) == 3

    def test_push_sample(self) -> None:
        """Test sample pushing to LSL stream."""
        streamer = LSLStreamer("test", 1000.0)
        mock_outlet = Mock()
        streamer.outlet = mock_outlet

        data = [1.0, 2.0, 3.0]

        streamer.push_sample(data)

        mock_outlet.push_sample.assert_called_once_with(data)
