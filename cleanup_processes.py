#!/usr/bin/env python3
"""Emergency cleanup script for PLUX processes."""

import subprocess
import sys

def cleanup_plux_processes():
    """Kill any remaining PLUX-related processes."""
    try:
        # Kill any bth_macprocess instances
        result = subprocess.run(
            ["pkill", "-9", "-f", "bth_macprocess"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Killed bth_macprocess instances")
        
        # Kill any Python processes running mobi-physio-api
        result = subprocess.run(
            ["pkill", "-9", "-f", "mobi-physio-api"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Killed mobi-physio-api processes")
            
        print("Cleanup complete")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_plux_processes()
