# MoBI-Physio-API

[![Tests](https://github.com/childmindresearch/MoBI-Physio-API/actions/workflows/test.yaml/badge.svg)](https://github.com/childmindresearch/MoBI-Physio-API/actions/workflows/test.yaml)
[![Documentation](https://github.com/childmindresearch/MoBI-Physio-API/actions/workflows/docs.yaml/badge.svg)](https://github.com/childmindresearch/MoBI-Physio-API/actions/workflows/docs.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![stability-stable](https://img.shields.io/badge/stability-stable-green.svg)
[![LGPL-2.1 License](https://img.shields.io/badge/license-LGPL--2.1-blue.svg)](https://github.com/childmindresearch/MoBI-Physio-API/blob/main/LICENSE)

A robust, cross-platform Python API for PLUX biosignals devices with automatic sensor detection and Lab Streaming Layer (LSL) integration.

## Features

- 🔍 **Automatic Sensor Detection**: Automatically detects and configures EMG, SpO2, EDA, ECG, ACC, and other PLUX sensors
- 🌐 **Cross-Platform Support**: Works on macOS (Intel & Apple Silicon), Windows, and Linux
- 📡 **LSL Streaming**: Real-time data streaming via Lab Streaming Layer with proper channel naming
- 🎯 **Type-Safe**: Full type hints and modern Python practices (Python 3.9+)
- 🖥️ **CLI Interface**: Easy-to-use command-line interface for quick streaming
- 🧪 **Production Ready**: Comprehensive testing, logging, and error handling

## Requirements

- **Python 3.10**: Required for PLUX SDK compatibility (only works with Python 3.10)
- **PLUX SDK**: Download and extract the PLUX-API-Python3 SDK to your project directory
- **LSL Library**: Lab Streaming Layer for real-time data streaming

## Installation

> **Note**: This package requires exactly Python 3.10 due to PLUX SDK compatibility requirements.

```bash
# Clone the repository
git clone https://github.com/childmindresearch/MoBI-Physio-API.git
cd MoBI-Physio-API

# Install with uv using Python 3.10
uv sync --python 3.10

# Test the installation
uv run --python 3.10 mobi-physio-api --help
```

### Development Installation

```bash
# Install with development dependencies
uv sync --python 3.10 --group dev

# Set up pre-commit hooks
uv run --python 3.10 pre-commit install
```

## Quick Start

### Command Line Interface

```bash
# Discover available devices
uv run --python 3.10 mobi-physio-api --discover

# Stream data from a specific device
uv run --python 3.10 mobi-physio-api --mac 00:07:80:8C:08:DF

# Stream with custom settings
uv run --python 3.10 mobi-physio-api --mac 00:07:80:8C:08:DF --rate 500 --stream-name "my_biosignals" -v

# Stream with custom connection timeout (device will keep trying to connect until timeout)
uv run --python 3.10 mobi-physio-api --mac 00:07:80:8C:08:DF --timeout 30
```

### Batch/Automated Usage

The CLI can be easily integrated into batch scripts or automated workflows:

```bash
#!/bin/bash
# example_batch.sh - Automated data collection script

# Set device MAC address
DEVICE_MAC="00:07:80:8C:08:DF"

# Start streaming for 10 minutes with timeout
echo "Starting data collection..."
timeout 600 uv run --python 3.10 mobi-physio-api --mac $DEVICE_MAC --rate 1000 --stream-name "study_data" --timeout 60

echo "Data collection complete."
```

```python
# example_automated.py - Python automation script
import subprocess
import sys

def start_streaming(mac_address: str, duration: int = 300):
    """Start PLUX streaming for specified duration."""
    cmd = [
        "uv", "run", "--python", "3.10",
        "mobi-physio-api",
        "--mac", mac_address,
        "--rate", "1000",
        "--stream-name", "automated_session",
        "--timeout", "60"
    ]
    
    try:
        # Run for specified duration
        result = subprocess.run(cmd, timeout=duration, capture_output=True, text=True)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Data collection completed after {duration} seconds")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = start_streaming("00:07:80:8C:08:DF", duration=600)  # 10 minutes
    sys.exit(0 if success else 1)
```

### Python API

```python
from mobi_physio_api import PluxDevice

# Initialize device
device = PluxDevice(
    mac_address="00:07:80:8C:08:DF",
    sampling_rate=1000.0,
    stream_name="biosignalsplux",
    connection_timeout=60  # 60 second timeout
)

# Auto-detect sensors
sensor_types = device.discover_sensors()
print(f"Detected sensors: {sensor_types}")

# Set up LSL streaming
device.setup_streaming()

# Start data acquisition
device.start_acquisition()  # Press Ctrl+C to stop
```

### Advanced Usage

```python
from mobi_physio_api import PluxDevice, SensorType
from pathlib import Path

# Custom SDK path and timeout
device = PluxDevice(
    mac_address="00:07:80:8C:08:DF",
    sampling_rate=1000.0,
    plux_sdk_path=Path("/path/to/PLUX-API-Python3"),
    connection_timeout=30  # 30 second timeout for faster failure detection
)

# Manual sensor configuration (if auto-detection fails)
device.channels = [1, 2, 3]
device.sensor_types = {
    1: SensorType.EMG,
    2: SensorType.ECG, 
    3: SensorType.EDA
}
```

## Supported Sensors

| Sensor Type | Description | Channels |
|-------------|-------------|----------|
| EMG | Electromyography | 1 channel |
| ECG | Electrocardiography | 1 channel |
| EDA | Electrodermal Activity | 1 channel |
| RSP | Respiration | 1 channel |
| SpO2 | Pulse Oximetry | 2 channels (RED, IR) |
| ACC | Accelerometer | 3 channels (X, Y, Z) |

## Project Structure

```
src/mobi_physio_api/
├── __init__.py              # Package initialization
├── cli.py                   # Command-line interface
├── device.py                # Main device interface
├── platform_detection.py   # Cross-platform SDK detection
├── sensor_detection.py     # Automatic sensor detection  
└── streaming.py             # LSL streaming functionality

tests/                       # Test suite
├── test_platform_detection.py
├── test_sensor_detection.py
└── test_streaming.py

.github/workflows/           # CI/CD workflows
├── test.yaml               # Testing & linting
└── docs.yaml               # Documentation
```

## Development

### Running Tests

```bash
# Run all tests
uv run --python 3.10 pytest

# Run with coverage
uv run --python 3.10 pytest --cov=src/mobi_physio_api

# Run specific test file
uv run --python 3.10 pytest tests/test_sensor_detection.py -v
```

### Code Quality

```bash
# Run linting
uv run --python 3.10 ruff check src/ tests/

# Run type checking  
uv run --python 3.10 mypy src/

# Run formatting
uv run --python 3.10 ruff format src/ tests/

# Check dependencies
uv run --python 3.10 deptry .
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

```bash
# Install hooks
uv run --python 3.10 pre-commit install

# Run manually
uv run --python 3.10 pre-commit run --all-files
```

## Troubleshooting

### Device Connection Issues

1. **Device not found**: Ensure the device is powered on and in pairing mode
2. **MAC address**: Use device discovery to find the correct MAC address
3. **Permissions**: On Linux, you may need to add your user to the `dialout` group
4. **Bluetooth**: Ensure the device is paired in your system's Bluetooth settings

### Platform-Specific Issues

**macOS:**
- For Apple Silicon Macs, ensure you're using the correct M1/M2 SDK binaries
- You may need to allow the application in Security & Privacy settings

**Windows:**
- Install Visual C++ Redistributable if you encounter DLL errors
- Ensure Bluetooth drivers are up to date
- MAC address format is automatically converted (use standard format like 00:07:80:8C:08:DF)

**Linux:**
- Install required system packages: `sudo apt-get install bluetooth libbluetooth-dev`
- Add user to bluetooth group: `sudo usermod -a -G bluetooth $USER`

### Import Errors

If you encounter import errors:

```bash
# Ensure the package is installed with Python 3.10
uv sync --python 3.10

# Check Python path
uv run --python 3.10 python -c "import sys; print(sys.path)"
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`  
3. Make your changes with tests
4. Run the test suite: `pytest`
5. Submit a pull request

## License

This project is licensed under the LGPL-2.1 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- PLUX Wireless Biosignals for the hardware and SDK
- Lab Streaming Layer (LSL) for real-time data streaming
- Child Mind Institute for project support

## Support

For issues and questions:
- 📁 Open an issue on GitHub
- 📧 Contact: dair@childmind.org
