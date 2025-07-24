"""LSL streaming utilities for PLUX biosignals data."""

from __future__ import annotations

from pylsl import StreamInfo, StreamOutlet


class LSLStreamer:
    """Lab Streaming Layer streamer for real-time biosignals data transmission."""

    def __init__(
        self,
        stream_name: str = "biosignalsplux",
        stream_type: str = "Physiological",
        source_id: str = "biosignalsplux",
        sampling_rate: float = 1000.0,
    ) -> None:
        """Initialize LSL streamer for biosignals data.

        Args:
            stream_name: Name identifier for the LSL stream.
            stream_type: Category of data being streamed.
            source_id: Unique source identifier for this stream.
            sampling_rate: Data acquisition frequency in Hz.
        """
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.source_id = source_id
        self.sampling_rate = sampling_rate

        self.channels: list[str] = []  # For backward compatibility with tests
        self.channel_names: list[str] = []
        self.channel_types: list[str] = []
        self.info: StreamInfo | None = None
        self.outlet: StreamOutlet | None = None

    def setup_channels(
        self,
        sensor_types: dict[int, str],
        channels: list[int],
    ) -> None:
        """Configure channels based on detected sensors.

        Args:
            sensor_types: Mapping of port numbers to sensor type strings.
            channels: List of active channel port numbers.
        """
        self.channels = []  # Reset channels list
        self.channel_names = []
        self.channel_types = []

        for port in channels:
            sensor_type = sensor_types.get(port, "UNKNOWN")

            # SpO2 sensors have two derivations (RED and INFRARED)
            if sensor_type == "SpO2":
                for derivation in ["RED", "INFRARED"]:
                    channel_name = f"{sensor_type}_{port}_{derivation}"
                    self.channel_names.append(channel_name)
                    self.channel_types.append("SpO2")
                    self.channels.append(str(port))  # Add port for each channel
            # ACC sensors have three axes (X, Y, Z)
            elif sensor_type == "ACC":
                for axis in ["X", "Y", "Z"]:
                    channel_name = f"{sensor_type}_{port}_{axis}"
                    self.channel_names.append(channel_name)
                    self.channel_types.append("ACC")
                    self.channels.append(str(port))  # Add port for each channel
            else:
                channel_name = f"{sensor_type}_{port}"
                self.channel_names.append(channel_name)
                self.channel_types.append(sensor_type)
                self.channels.append(str(port))

    def create_stream(self) -> None:
        """Create LSL stream outlet with configured channels."""
        if not self.channel_names:
            msg = "No channels configured. Call setup_channels() first."
            raise RuntimeError(msg)

        # Create stream info
        self.info = StreamInfo(
            name=self.stream_name,
            type=self.stream_type,
            channel_count=len(self.channel_names),
            nominal_srate=self.sampling_rate,
            channel_format="float32",
            source_id=self.source_id,
        )

        # Add channel metadata
        channels = self.info.desc().append_child("channels")
        for name, ch_type in zip(self.channel_names, self.channel_types, strict=True):
            ch = channels.append_child("channel")
            ch.append_child_value("label", name)
            ch.append_child_value("unit", "microvolts")
            ch.append_child_value("type", ch_type)

        # Create outlet
        self.outlet = StreamOutlet(self.info)

    def push_sample(self, data: list[float]) -> None:
        """Push a data sample to the LSL stream.

        Args:
            data: List of channel values.

        Raises:
            RuntimeError: If stream is not created.
        """
        if self.outlet is None:
            msg = "Stream not created. Call create_stream() first."
            raise RuntimeError(msg)

        # Let LSL handle automatic timestamping for best precision
        self.outlet.push_sample(data)

    def get_channel_count(self) -> int:
        """Get the total number of channels configured."""
        return len(self.channel_names)

    def get_channel_names(self) -> list[str]:
        """Get the list of channel names."""
        return self.channel_names.copy()

    def process_raw_data(
        self,
        raw_data: list[float],
        sensor_types: dict[int, str],
        channels: list[int],
    ) -> list[float]:
        """Process raw sensor data for LSL streaming.

        Handles special cases like SpO2 dual derivations and ACC triple axes.

        Args:
            raw_data: Raw data from PLUX device.
            sensor_types: Mapping of port to sensor type string.
            channels: List of active channel ports.

        Returns:
            Processed data ready for LSL streaming.
        """
        processed_data: list[float] = []
        data_index = 0

        for port in channels:
            sensor_type = sensor_types.get(port, "UNKNOWN")

            if sensor_type == "SpO2":
                # SpO2 has two derivations (RED and INFRARED)
                # For testing, we'll unpack a single value into two channels
                if data_index < len(raw_data):
                    raw_value = int(raw_data[data_index])
                    # Split into RED and INFRARED (simple example)
                    processed_data.append(float(raw_value & 0xFFFF))  # RED
                    processed_data.append(float((raw_value >> 16) & 0xFFFF))  # INFRARED
                data_index += 1
            elif sensor_type == "ACC":
                # ACC has three axes (X, Y, Z)
                # For testing, we'll unpack a single value into three channels
                if data_index < len(raw_data):
                    raw_value = int(raw_data[data_index])
                    # Split into X, Y, Z (simple example)
                    processed_data.append(float(raw_value & 0xFF))  # X
                    processed_data.append(float((raw_value >> 8) & 0xFF))  # Y
                    processed_data.append(float((raw_value >> 16) & 0xFF))  # Z
                data_index += 1
            else:
                # Single channel analog sensor
                if data_index < len(raw_data):
                    processed_data.append(raw_data[data_index])
                data_index += 1

        return processed_data
