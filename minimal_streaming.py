#!/usr/bin/env python3
"""Minimal working PLUX streaming - no bloat, just core functionality."""

import platform
import sys
import time
import signal
from pylsl import StreamInfo, StreamOutlet

# Set up PLUX import path
def setup_plux():
    system = platform.system()
    if system == "Darwin":  # macOS
        machine = platform.machine()
        python_version = "".join(platform.python_version().split(".")[:2])
        if machine == "arm64":  # M1/M2
            plux_path = f"PLUX-API-Python3/M1_{python_version}"
            # Fallback paths
            for fallback in ["M1_312", "M1_311", "M1_310"]:
                try:
                    sys.path.append(f"PLUX-API-Python3/{fallback}")
                    import plux
                    print(f"Using PLUX path: PLUX-API-Python3/{fallback}")
                    return plux
                except ImportError:
                    continue
        sys.path.append(plux_path)
    elif system == "Windows":
        python_version = "".join(platform.python_version().split(".")[:2])
        arch = platform.architecture()[0][:2]
        sys.path.append(f"PLUX-API-Python3/Win{arch}_{python_version}")
    else:  # Linux
        sys.path.append("PLUX-API-Python3/Linux64")
    
    import plux
    return plux

plux = setup_plux()

# Configuration
MAC_ADDRESS = "00:07:80:8C:08:DF"  # Keep original format for macOS
SAMPLING_RATE = 1000
running = False

class MinimalDevice(plux.SignalsDev):
    def __init__(self, mac_address):
        # Connect to device
        print(f"Connecting to {mac_address}...")
        
        # Auto-detect sensors
        print("Detecting sensors...")
        try:
            sensors = self.getSensors()
            print(f"Found {len(sensors)} sensors")
            
            if not sensors:
                print("No sensors found, using fallback ports [1,2,3]")
                self.channels = [1, 2, 3]
                self.sensor_types = {1: "RSP", 2: "EMG", 3: "EDA"}
            else:
                self.channels = list(sensors.keys())
                self.sensor_types = {}
                for port, sensor in sensors.items():
                    # Sensor type detection based on PLUX documentation
                    type_map = {
                        0: "EMG",    # Electromyography  
                        1: "ECG",    # Electrocardiography
                        2: "EDA",    # Electrodermal Activity (GSR)
                        3: "EEG",    # Electroencephalography
                        4: "ACC",    # Accelerometer
                        7: "RSP",    # Respiratory
                        69: "SpO2",  # Pulse oximetry
                        70: "PPG"    # Photoplethysmography
                    }
                    sensor_type = type_map.get(sensor.type, f"Unknown_Type{sensor.type}")
                    self.sensor_types[port] = sensor_type
                    print(f"  Port {port}: {sensor_type} (type={sensor.type})")
        except Exception as e:
            print(f"Sensor detection failed: {e}")
            print("Using fallback ports [1,2,3]")
            self.channels = [1, 2, 3]
            self.sensor_types = {1: "RSP", 2: "EMG", 3: "EDA"}
        
        # Create LSL stream
        channel_names = [f"{self.sensor_types[port]}_CH{port}" for port in self.channels]
        print(f"Creating LSL stream with channels: {channel_names}")
        
        info = StreamInfo(
            name="biosignalsplux",
            type="Physiological",
            channel_count=len(channel_names),
            nominal_srate=SAMPLING_RATE,
            channel_format="float32",
            source_id="biosignalsplux"
        )
        
        self.outlet = StreamOutlet(info)
        self.sample_count = 0
        self.last_print = time.time()
    
    def onRawFrame(self, seq, data):
        """Handle incoming data - called by device.loop()"""
        global running
        if not running:
            return True  # Stop
        
        # Push data to LSL
        self.outlet.push_sample(data[:len(self.channels)])
        self.sample_count += 1
        
        # Progress indicator every 1000 samples
        if self.sample_count % 1000 == 0:
            elapsed = time.time() - self.last_print
            rate = 1000 / elapsed if elapsed > 0 else 0
            print(f"Streaming: {self.sample_count} samples, {rate:.1f} Hz")
            self.last_print = time.time()
        
        return False  # Continue
    
    def start_streaming(self):
        """Start acquisition and streaming"""
        global running
        print(f"Starting acquisition on channels: {self.channels}")
        print(f"Sensor types: {list(self.sensor_types.values())}")
        print("Press Ctrl+C to stop...")
        
        # Create sources
        sources = []
        for port in self.channels:
            source = plux.Source()
            source.port = port
            source.freqDivisor = 1
            source.nBits = 16
            sources.append(source)
        
        running = True
        self.start(SAMPLING_RATE, sources)
        
        try:
            # This should work without infinite loops
            self.loop()
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            running = False
            try:
                self.stop()
                self.close()
            except:
                pass

def signal_handler(signum, frame):
    global running
    print("\nReceived interrupt, stopping...")
    running = False

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        device = MinimalDevice(MAC_ADDRESS)
        device.start_streaming()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
