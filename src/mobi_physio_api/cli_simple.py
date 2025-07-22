"""Simplified CLI for PLUX device streaming."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mobi_physio_api.device import PluxDevice
from mobi_physio_api.utils import setup_signal_handler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for PLUX device streaming CLI.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Stream PLUX biosignals to LSL",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--mac",
        required=True,
        help="Device MAC address (e.g., 00:07:80:8C:08:DF)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1000.0,
        help="Sampling rate in Hz",
    )
    parser.add_argument(
        "--stream-name",
        default="biosignalsplux",
        help="LSL stream name",
    )
    parser.add_argument(
        "--sdk-path",
        type=Path,
        help="Path to PLUX SDK directory",
    )
    parser.add_argument(
        "--sensors",
        help=(
            "Manual sensor mapping as port:type pairs. "
            "Example: --sensors 1:EMG,2:RSP,3:EDA,5:ECG,9:SpO2"
        ),
    )

    args = parser.parse_args()

    # Parse manual sensor mapping if provided
    manual_sensor_map = {}
    if args.sensors:
        try:
            for mapping in args.sensors.split(","):
                port_str, sensor_type = mapping.strip().split(":")
                port = int(port_str)
                manual_sensor_map[port] = sensor_type.upper()
            logger.info("Manual sensor mapping: %s", manual_sensor_map)
        except ValueError as e:
            logger.error("Invalid sensor mapping format: %s", e)
            logger.error("Expected format: --sensors 1:EMG,2:RSP,3:EDA")
            return 1

    try:
        logger.info("Initializing PLUX device...")
        logger.info("Device MAC: %s", args.mac)
        logger.info("Sampling rate: %s Hz", args.rate)
        logger.info("Stream name: %s", args.stream_name)

        # Create device
        device = PluxDevice(
            mac_address=args.mac,
            sampling_rate=args.rate,
            stream_name=args.stream_name,
            plux_sdk_path=args.sdk_path,
            manual_sensor_map=manual_sensor_map,
        )

        logger.info("Device initialized successfully!")

        # Set up signal handler for graceful shutdown
        setup_signal_handler(device)

        # Connect and start streaming
        logger.info("Connecting and setting up streaming...")
        device.connect_and_setup()

        logger.info("Starting streaming...")
        device.start_streaming()

    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 0
    except Exception as e:
        logger.error("Error: %s", e)
        logger.error("Error type: %s", type(e).__name__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
