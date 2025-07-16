# /// script
# dependencies = [
#   "pylsl"
# ]
# ///

import platform
import sys
import time
import signal
import subprocess
from pylsl import StreamInfo, StreamOutlet

# Global device reference for cleanup
device_instance = None

# Detect correct platform path for PLUX SDK
def get_plux_path():
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Check if running on Apple Silicon (M1/M2) or Intel
        machine = platform.machine()
        python_version = ''.join(platform.python_version().split('.')[:2])
        
        if machine == "arm64":  # Apple Silicon (M1/M2)
            # Try M1 directories based on Python version
            m1_options = [f"M1_{python_version}", "M1_312", "M1_311", "M1_310", "M1_39", "M1_37"]
            for option in m1_options:
                import os
                if os.path.exists(f"PLUX-API-Python3/{option}"):
                    return option
        else:  # Intel Mac
            # Try Intel directories based on Python version
            intel_options = [f"MacOS/Intel{python_version}", "MacOS/Intel310", "MacOS/Intel39", "MacOS/Intel38", "MacOS/Intel37"]
            for option in intel_options:
                import os
                if os.path.exists(f"PLUX-API-Python3/{option}"):
                    return option
    
    elif system == "Linux":
        return "Linux64"
    
    elif system == "Windows":
        python_version = ''.join(platform.python_version().split('.')[:2])
        arch = platform.architecture()[0][:2]
        return f"Win{arch}_{python_version}"
    
    # Fallback - shouldn't reach here
    raise RuntimeError(f"Unsupported platform: {system}")

plux_path = get_plux_path()
print(f"Using PLUX path: {plux_path}")
sys.path.append(f"PLUX-API-Python3/{plux_path}")

import plux  # Import after setting sys.path

# Define your device MAC address
# Automatically format MAC address based on OS
base_mac = '00:07:80:8C:08:DF'  # Your device's base MAC address
if platform.system() == "Windows":
    DEVICE_MAC = f'BTH{base_mac}'  # Windows format: BTH00:07:80:8C:08:DF
else:
    DEVICE_MAC = base_mac.replace(':', '-')  # macOS format: 00-07-80-8C-08-DF


# Sampling rate
SAMPLING_RATE = 1000  # Hz

def detect_sensor_type(sensor, properties, port):
    """
    Automatically detect sensor type based on sensor properties and characteristics
    """
    # Known sensor type mappings from PLUX documentation
    type_map = {
        0: 'EMG',    # Electromyography
        1: 'ECG',    # Electrocardiography  
        2: 'EDA',    # Electrodermal Activity (GSR)
        3: 'EEG',    # Electroencephalography
        4: 'ACC',    # Accelerometer
        5: 'GYRO',   # Gyroscope
        6: 'MAG',    # Magnetometer
        7: 'RSP',    # Respiratory
        8: 'PZT',    # Piezoelectric
        9: 'TEMP',   # Temperature
        69: 'SpO2',  # Pulse oximetry
        70: 'PPG',   # Photoplethysmography
    }
    
    # Get base sensor type from the type field
    base_type = type_map.get(sensor.type, f'Unknown_Type{sensor.type}')
    
    # For accelerometers, try to determine axis based on characteristics, port, or other info
    if sensor.type == 4 or base_type == 'ACC':
        characteristics = sensor.characteristics
        
        # Look for axis information in characteristics
        if isinstance(characteristics, dict):
            if 'axis' in characteristics:
                axis = characteristics['axis']
                return f'ACC_{axis}'
            elif 'channel' in characteristics:
                channel = characteristics['channel']
                axis_map = {0: 'X', 1: 'Y', 2: 'Z'}
                axis = axis_map.get(channel, channel)
                return f'ACC_{axis}'
        
        # Try to infer axis from port number (common convention: consecutive ports)
        # This is heuristic and may not always be accurate
        if port in [5, 6, 7]:  # Common accelerometer port arrangement
            axis_map = {5: 'X', 6: 'Y', 7: 'Z'}
            return f'ACC_{axis_map[port]}'
        elif port in [8, 9, 10]:  # Alternative arrangement
            axis_map = {8: 'X', 9: 'Y', 10: 'Z'}
            return f'ACC_{axis_map[port]}'
        
        # If no axis info available, just return ACC
        return 'ACC'
    
    # Special handling for digital sensors
    if sensor.type == 69:  # SpO2
        return 'SpO2'
    
    # Try to enhance detection using productID or other properties
    product_id = "Unknown"
    if hasattr(sensor, 'productID'):
        product_id = str(sensor.productID)
    elif isinstance(properties, dict) and 'productID' in properties:
        product_id = str(properties['productID'])
    
    # Enhanced detection based on productID patterns (if available)
    if product_id != "Unknown":
        product_id_lower = product_id.lower()
        if 'ecg' in product_id_lower or 'electrocardiogram' in product_id_lower:
            return 'ECG'
        elif 'emg' in product_id_lower or 'electromyogram' in product_id_lower:
            return 'EMG'
        elif 'eda' in product_id_lower or 'gsr' in product_id_lower or 'galvanic' in product_id_lower:
            return 'EDA'
        elif 'spo2' in product_id_lower or 'oximetry' in product_id_lower:
            return 'SpO2'
        elif 'acc' in product_id_lower or 'accelerometer' in product_id_lower:
            return 'ACC'
        elif 'ppg' in product_id_lower or 'photoplethysmography' in product_id_lower:
            return 'PPG'
        elif 'resp' in product_id_lower or 'respiratory' in product_id_lower:
            return 'RSP'
    
    # For other sensors, use the base type from type mapping
    return base_type

def get_sensor_info(device):
    """
    Get sensor information and automatically detect channels
    Returns: (channels, sensor_types, sensor_info, sources)
    """
    try:
        sensors = device.getSensors()
        print(f"Auto-detected {len(sensors)} sensors:")
        
        # Get device properties for additional sensor information
        try:
            properties = device.getProperties()
            print(f"Device properties: {properties}")
        except Exception as e:
            print(f"Could not get device properties: {e}")
            properties = {}
        
        channels = []
        sensor_types = {}
        sensor_info = {}
        sources = []  # Store plux.Source objects for proper configuration
        
        for port, sensor in sensors.items():
            channels.append(port)
            
            # Print raw sensor information for debugging
            print(f"  Port {port}: RAW INFO")
            print(f"    Type: {sensor.type}")
            print(f"    Class: {sensor.clas}")
            print(f"    Serial: {sensor.serialNum}")
            print(f"    HW Version: {sensor.hwVersion}")
            print(f"    Characteristics: {sensor.characteristics}")
            
            # Try to get productID from sensor or device properties
            product_id = "Unknown"
            if hasattr(sensor, 'productID'):
                product_id = sensor.productID
            elif 'productID' in properties:
                product_id = properties['productID']
            print(f"    Product ID: {product_id}")
            
            # Automatically detect sensor type based on actual sensor properties
            sensor_type = detect_sensor_type(sensor, properties, port)
            sensor_types[port] = sensor_type
            
            print(f"    🎯 DETECTED TYPE: {sensor_type}")
            
            # Store detailed sensor info
            sensor_info[port] = {
                'type': sensor.type,
                'class': sensor.clas,
                'characteristics': sensor.characteristics,
                'serial': sensor.serialNum,
                'hw_version': sensor.hwVersion,
                'product_id': product_id
            }
            
            # Create appropriate source configuration
            if sensor.type == 69:  # SpO2 sensor - Digital channel
                print("    🔧 Configured as DIGITAL channel (SpO2 with RED/INFRARED)")
                source = plux.Source()
                source.port = port
                source.freqDivisor = 1  # No subsampling
                source.nBits = 16      # 16-bit resolution
                source.chMask = 0x03   # Both RED and INFRARED derivations (binary 11)
                sources.append(source)
            else:  # Analog sensors (EMG, ECG, ACC, etc.)
                print("    🔧 Configured as ANALOG channel")
                source = plux.Source()
                source.port = port
                source.freqDivisor = 1  # No subsampling
                source.nBits = 16      # 16-bit resolution
                sources.append(source)
            print()
        
        return channels, sensor_types, sensor_info, sources
        
    except Exception as e:
        print(f"Warning: Could not auto-detect sensors: {e}")
        print("Using fallback channels [1, 2, 3]")
        
        # Fallback sources
        fallback_sources = []
        for port in [1, 2, 3]:
            source = plux.Source()
            source.port = port
            source.freqDivisor = 1
            source.nBits = 16
            fallback_sources.append(source)
        
        return [1, 2, 3], {1: 'RSP', 2: 'EMG', 3: 'EDA'}, {}, fallback_sources


class MyDevice(plux.SignalsDev):
    def __init__(self, mac):
        # Initialize PLUX device without calling parent __init__
        # The PLUX library seems to handle initialization differently
        self.mac = mac
        self.sample_count = 0
        self.last_print_time = time.time()
        self.frequency = SAMPLING_RATE
        self.running = False  # Flag to control the loop
        
        # Auto-detect sensors and channels
        print("Auto-detecting sensors...")
        self.channels, self.sensor_types, self.sensor_info, self.sources = get_sensor_info(self)
        
        # Create channel names for LSL
        self.lsl_channel_names = []  # Store for later reference
        for port in self.channels:
            sensor_type = self.sensor_types.get(port, f'Port{port}')
            # SpO2 sensors have two derivations (RED and INFRARED)
            if self.sensor_types.get(port) == 'SpO2':
                self.lsl_channel_names.append(f"{sensor_type}_Port{port}_RED")
                self.lsl_channel_names.append(f"{sensor_type}_Port{port}_INFRARED")
            else:
                self.lsl_channel_names.append(f"{sensor_type}_Port{port}")
        
        # Set up a single LSL stream with multiple channels
        self.lsl_info = StreamInfo(
            name="biosignalsplux",
            type="Physiological",
            channel_count=len(self.lsl_channel_names),  # Updated to account for SpO2 dual channels
            nominal_srate=SAMPLING_RATE,
            channel_format="float32",
            source_id="biosignalsplux"
        )
        
        # Add channel names to LSL stream
        channels = self.lsl_info.desc().append_child("channels")
        for i, name in enumerate(self.lsl_channel_names):
            ch = channels.append_child("channel")
            ch.append_child_value("label", name)
            ch.append_child_value("unit", "microvolts")
            # Determine channel type based on name
            if "SpO2" in name:
                ch.append_child_value("type", "SpO2")
            elif "ACC" in name:
                ch.append_child_value("type", "Accelerometer")
            elif "RSP" in name:
                ch.append_child_value("type", "Respiratory")
            else:
                ch.append_child_value("type", self.sensor_types.get(self.channels[i % len(self.channels)], "Unknown"))
        
        self.lsl_outlet = StreamOutlet(self.lsl_info)
        print(f"LSL stream created with {len(self.lsl_channel_names)} channels: {self.lsl_channel_names}")

    def onRawFrame(self, nSeq, data):
        """Called automatically by loop(). Processes incoming data."""
        if not self.running:
            return True  # Stop the loop if running flag is False
            
        timestamp = time.time()
        self.sample_count += 1

        # Process data for LSL - handle SpO2 dual channels
        lsl_data = []
        data_index = 0
        
        for port in self.channels:
            if self.sensor_types.get(port) == 'SpO2':
                # SpO2 has two derivations (RED and INFRARED)
                if data_index < len(data):
                    lsl_data.append(data[data_index])  # RED
                if data_index + 1 < len(data):
                    lsl_data.append(data[data_index + 1])  # INFRARED
                data_index += 2
            else:
                # Single channel analog sensor
                if data_index < len(data):
                    lsl_data.append(data[data_index])
                data_index += 1

        # Push processed data to the LSL stream
        self.lsl_outlet.push_sample(lsl_data, timestamp)

        # Print debug information every 1000 samples
        if self.sample_count % 1000 == 0:
            elapsed = time.time() - self.last_print_time
            actual_rate = 1000 / elapsed if elapsed > 0 else 0
            print(f"Sample #{self.sample_count}")
            print(f"  Sequence: {nSeq}")
            print(f"  Raw Data: {data}")
            print(f"  LSL Data: {lsl_data}")
            print(f"  Ports: {self.channels}")
            print(f"  Sensor types: {list(self.sensor_types.values())}")
            print(f"  LSL Channel Labels: {self.lsl_channel_names}")
            print(f"  Actual rate: {actual_rate:.1f} Hz")
            print(f"  Timestamp: {timestamp}")
            print("-" * 50)
            self.last_print_time = time.time()

        # Return False to keep the loop running, True to stop
        return not self.running

    def start_acquisition(self):
        print(f"Starting acquisition on auto-detected ports: {self.channels}")
        print(f"Sensor types: {self.sensor_types}")
        print(f"LSL Channel Labels: {self.lsl_channel_names}")
        print(f"Sampling rate: {SAMPLING_RATE} Hz")
        print(f"Device MAC: {DEVICE_MAC}")

        # Start acquisition with auto-detected sources (handles analog/digital properly)
        print("Starting device acquisition...")
        self.running = True  # Set running flag
        self.start(self.frequency, self.sources)  # Use sources instead of channels + resolution
        print("Device started. Entering streaming loop...")
        print("💡 Press Ctrl+C to stop, or press 'q' + Enter to quit...")
        
        # Start a separate thread to check for keyboard input as backup
        import threading
        
        def check_keyboard_input():
            while self.running:
                try:
                    user_input = input().strip().lower()
                    if user_input == 'q':
                        print("\n🛑 'q' pressed - shutting down...")
                        self.running = False
                        break
                except EOFError:
                    # Handle case where input is not available (e.g., piped input)
                    break
                except KeyboardInterrupt:
                    # Handle Ctrl+C in input thread
                    break
        
        input_thread = threading.Thread(target=check_keyboard_input, daemon=True)
        input_thread.start()
        
        self.loop()  # Calls onRawFrame() internally until it returns True

    def stop_acquisition(self):
        print("Stopping acquisition...")
        self.running = False  # Signal the loop to stop
        try:
            self.stop()
            self.close()
        except Exception as e:
            print(f"Warning during stop: {e}")


def cleanup_processes():
    """Clean up any stuck PLUX processes"""
    print("\n🧹 Cleaning up PLUX processes...")
    try:
        subprocess.run(['pkill', '-f', 'bth_macprocess'], check=False)
        subprocess.run(['pkill', '-f', 'plux'], check=False)
        print("✓ Cleanup completed")
    except Exception as e:
        print(f"Cleanup warning: {e}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Shutdown requested (Ctrl+C detected)...")
    
    global device_instance
    if device_instance:
        try:
            print("📱 Stopping device acquisition...")
            device_instance.running = False  # Signal the loop to stop
            time.sleep(1)  # Give it a moment to stop
            device_instance.stop()
            device_instance.close()
            print("✓ Device stopped successfully")
        except Exception as e:
            print(f"Warning during device shutdown: {e}")
    
    cleanup_processes()
    print("👋 Goodbye!")
    sys.exit(0)

# Set up signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

def main():
    print("Initializing PLUX device with auto-detection...")
    print(f"Device MAC: {DEVICE_MAC}")
    print("\n💡 Use Ctrl+C to stop the acquisition properly (NOT Ctrl+Z)")
    print("=" * 60)
    
    global device_instance  # Declare global instance for cleanup
    device_instance = None
    
    try:
        device = MyDevice(DEVICE_MAC)
        device_instance = device  # Assign to global instance
        print("Device initialized successfully!")
        device.start_acquisition()
    except KeyboardInterrupt:
        print("\nUser interrupted.")
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        print("\nTroubleshooting tips:")
        print("1. Make sure the device is turned on and in pairing mode")
        print("2. Try pairing the device manually in macOS Bluetooth settings")
        print("3. Check if the MAC address is correct")
        print("4. Make sure no other applications are using the device")
        print("5. If you get 'Failed bootstrap checkin' error, run:")
        print("   pkill -f bth_macprocess")
    finally:
        if device_instance:
            try:
                print("🧹 Final cleanup...")
                device_instance.stop_acquisition()
            except Exception:
                pass
        cleanup_processes()


if __name__ == "__main__":
    main()
