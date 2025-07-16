"""Command-line interface for MoBI-Physio-API."""

import argparse
import logging
import platform
import sys
from pathlib import Path

from mobi_physio_api.device import PluxDevice


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration.

    Args:
        verbose: Enable verbose logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def discover_devices(sdk_path: Path | None = None) -> list[str]:
    """Discover available PLUX devices.

    Args:
        sdk_path: Path to PLUX SDK directory.

    Returns:
        List of discovered device MAC addresses.
    """
    logger = logging.getLogger(__name__)
    logger.info("Scanning for PLUX devices...")

    try:
        # Set up PLUX SDK import path first
        from mobi_physio_api.platform_detection import setup_plux_import_path

        setup_plux_import_path(sdk_path)

        # Import PLUX after setting up path
        import plux  # type: ignore[import-untyped]

        devices = plux.BaseDev.findDevices()
        if devices:
            logger.info("Found %d device(s):", len(devices))
            device_list = []
            for i, device in enumerate(devices):
                device_str = str(device)
                logger.info("  %d. %s", i + 1, device_str)
                device_list.append(device_str)
            return device_list

        logger.info("No devices found.")
        return []
    except ImportError as e:
        logger.error("PLUX library not available: %s", e)
        return []
    except Exception as e:
        logger.error("Error during device discovery: %s", e)
        return []


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        description="MoBI-Physio-API: Stream PLUX biosignals data via LSL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --discover                      # Discover available devices
  %(prog)s --mac 00:07:80:8C:08:DF         # Stream from specific device
  %(prog)s --mac 00:07:80:8C:08:DF -v      # Stream with verbose logging
  %(prog)s --mac 00:07:80:8C:08:DF --timeout 30  # Custom timeout
        """,
    )

    parser.add_argument(
        "--mac",
        type=str,
        help="Device MAC address (required for streaming)",
    )

    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover available PLUX devices and exit",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=1000.0,
        help="Sampling rate in Hz (default: 1000.0)",
    )

    parser.add_argument(
        "--stream-name",
        type=str,
        default="biosignalsplux",
        help="LSL stream name (default: biosignalsplux)",
    )

    parser.add_argument(
        "--sdk-path",
        type=Path,
        help="Path to PLUX SDK directory (default: current directory)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Connection timeout in seconds (default: 60)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Handle device discovery
    if args.discover:
        logger.info("Starting device discovery...")
        devices = discover_devices(args.sdk_path)
        if devices:
            logger.info("Discovered devices:")
            for device_mac in devices:
                logger.info("  %s", device_mac)
        else:
            logger.info("No devices found.")
        return 0

    # Validate MAC address for streaming
    if not args.mac:
        logger.error("MAC address is required for streaming. Use --mac or --discover")
        parser.print_help()
        return 1

    # Initialize and start device
    logger.info("Initializing PLUX device...")
    logger.info("Device MAC: %s", args.mac)
    logger.info("Sampling rate: %s Hz", args.rate)
    logger.info("Stream name: %s", args.stream_name)
    logger.info("Connection timeout: %s seconds", args.timeout)

    try:
        device = PluxDevice(
            mac_address=args.mac,
            sampling_rate=args.rate,
            stream_name=args.stream_name,
            plux_sdk_path=args.sdk_path,
            connection_timeout=args.timeout,
        )

        logger.info("Device initialized successfully!")

        # Discover sensors
        logger.info("Discovering sensors...")
        sensor_types = device.discover_sensors()
        logger.info("Detected sensors: %s", sensor_types)

        # Set up streaming
        logger.info("Setting up LSL streaming...")
        device.setup_streaming()

        # Start acquisition
        logger.info("Starting data acquisition...")
        device.start_acquisition()

    except KeyboardInterrupt:
        logger.info("User interrupted.")
        return 0
    except Exception as e:
        logger.error("Error: %s", e)
        logger.error("Error type: %s", type(e).__name__)

        if args.verbose:
            import traceback

            traceback.print_exc()

        logger.info("Troubleshooting tips:")
        logger.info("1. Make sure the device is turned on and in pairing mode")
        logger.info("2. Try pairing the device manually in system Bluetooth settings")
        logger.info("3. Check if the MAC address is correct")
        logger.info("4. Make sure no other applications are using the device")
        logger.info("5. Use --discover to find available devices")

        # Platform-specific tips
        if platform.system() == "Windows":
            logger.info("6. Windows: Check 'Device Manager' → 'Bluetooth' for pairing")
            logger.info("7. Windows: Ensure Bluetooth is enabled in Windows settings")
        elif platform.system() == "Darwin":  # macOS
            logger.info("6. macOS: Check 'System Preferences' → 'Bluetooth'")
            logger.info("7. macOS: Try removing and re-pairing the device")
        else:  # Linux
            logger.info("6. Linux: Check with 'bluetoothctl' or 'bluez-utils'")
            logger.info("7. Linux: Ensure your user is in the 'bluetooth' group")

        return 1


if __name__ == "__main__":
    sys.exit(main())
