#!/usr/bin/env python3
"""Test script to simulate streaming and test Ctrl+C behavior."""

import signal
import sys
import time
import threading

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("Ctrl+C received! Exiting immediately...")
    sys.exit(0)

def mock_streaming():
    """Simulate streaming data."""
    print("Starting mock streaming... Press Ctrl+C to test shutdown")
    print("Streaming data...")
    
    for i in range(10000):
        print(f"Sample {i}: [42.5, 128.0, 98.2]")
        time.sleep(0.001)  # 1000 Hz simulation
        
        if i % 1000 == 0:
            print(f"Streamed {i} samples")

if __name__ == "__main__":
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        mock_streaming()
    except KeyboardInterrupt:
        print("KeyboardInterrupt caught in main")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Test complete")
