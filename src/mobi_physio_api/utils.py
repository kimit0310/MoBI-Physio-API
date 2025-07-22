"""Utility functions for signal handling and process management."""

import logging
import os
import signal
import subprocess
import threading
from types import FrameType
from typing import Protocol


class DeviceProtocol(Protocol):
    """Protocol for device instances that can be shut down."""

    running: bool


logger = logging.getLogger(__name__)

# Global flag for emergency shutdown
_emergency_shutdown = threading.Event()


def cleanup_plux_processes() -> None:
    """Clean up any stuck PLUX background processes."""
    logger.info("Cleaning up PLUX processes...")
    try:
        subprocess.run(["pkill", "-f", "bth_macprocess"], check=False)
        subprocess.run(["pkill", "-f", "plux"], check=False)
        logger.info("Cleanup completed")
    except Exception as e:
        logger.warning("Cleanup warning: %s", e)


def setup_signal_handler(device_instance: DeviceProtocol | None) -> None:
    """Configure signal handler for graceful shutdown on Ctrl+C.

    Args:
        device_instance: Device instance to clean up on shutdown.
    """

    def signal_handler(sig: int, frame: FrameType | None) -> None:
        """Handle Ctrl+C signal for graceful shutdown."""
        logger.info("Interrupt received (Ctrl+C), shutting down immediately...")

        # Set global emergency flag
        _emergency_shutdown.set()

        # Stop device if available
        if device_instance and hasattr(device_instance, "running"):
            device_instance.running = False

        # Clean up processes
        cleanup_plux_processes()

        # Force exit immediately
        logger.info("Shutdown initiated. Exiting...")
        os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)


def is_emergency_shutdown() -> bool:
    """Check if emergency shutdown flag is set.

    Returns:
        True if shutdown is in progress, False otherwise.
    """
    return _emergency_shutdown.is_set()


def format_mac_address(mac_address: str) -> str:
    """Format MAC address for platform-specific PLUX connection.

    Args:
        mac_address: Raw MAC address string.

    Returns:
        Formatted MAC address (adds BTH prefix on Windows).
    """
    import platform

    if platform.system() == "Windows" and not mac_address.startswith("BTH"):
        return f"BTH{mac_address}"
    return mac_address  # Keep original format for macOS/Linux
