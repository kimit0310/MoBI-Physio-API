"""Platform detection utilities for PLUX SDK path resolution."""

import platform
from pathlib import Path


def get_plux_sdk_path() -> str:
    """Get the correct PLUX SDK path based on the current platform and Python version.

    Returns:
        The relative path to the appropriate PLUX SDK directory.

    Raises:
        RuntimeError: If the platform is unsupported or no compatible SDK found.
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        return _get_macos_path()
    if system == "Linux":
        return "PLUX-API-Python3/Linux64"
    if system == "Windows":
        return _get_windows_path()

    msg = f"Unsupported platform: {system}"
    raise RuntimeError(msg)


def _get_macos_path() -> str:
    """Get macOS-specific PLUX SDK path."""
    machine = platform.machine()
    python_version = "".join(platform.python_version().split(".")[:2])

    if machine == "arm64":  # Apple Silicon (M1/M2)
        m1_options = [
            f"M1_{python_version}",
            "M1_312",
            "M1_311",
            "M1_310",
            "M1_39",
            "M1_37",
        ]
        for option in m1_options:
            if Path(f"PLUX-API-Python3/{option}").exists():
                return f"PLUX-API-Python3/{option}"
    else:  # Intel Mac
        intel_options = [
            f"MacOS/Intel{python_version}",
            "MacOS/Intel310",
            "MacOS/Intel39",
            "MacOS/Intel38",
            "MacOS/Intel37",
        ]
        for option in intel_options:
            if Path(f"PLUX-API-Python3/{option}").exists():
                return f"PLUX-API-Python3/{option}"

    msg = f"No compatible PLUX SDK found for macOS {machine} Python {python_version}"
    raise RuntimeError(msg)


def _get_windows_path() -> str:
    """Get Windows-specific PLUX SDK path."""
    python_version = "".join(platform.python_version().split(".")[:2])
    arch = platform.architecture()[0][:2]
    return f"PLUX-API-Python3/Win{arch}_{python_version}"


def setup_plux_import_path(base_path: Path | None = None) -> str:
    """Set up the import path for the PLUX library.

    Args:
        base_path: Base directory containing PLUX-API-Python3.
                  Defaults to current directory.

    Returns:
        The path that was added to sys.path.

    Raises:
        RuntimeError: If the PLUX SDK cannot be found or imported.
    """
    import sys

    if base_path is None:
        base_path = Path.cwd()

    plux_relative_path = get_plux_sdk_path()
    plux_full_path = base_path / plux_relative_path

    if not plux_full_path.exists():
        msg = f"PLUX SDK not found at {plux_full_path}"
        raise RuntimeError(msg)

    plux_path_str = str(plux_full_path)
    if plux_path_str not in sys.path:
        sys.path.insert(0, plux_path_str)

    return plux_path_str
