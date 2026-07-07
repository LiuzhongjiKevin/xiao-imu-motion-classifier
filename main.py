"""BLE IMU receiver + real-time motion state classifier.

Connects to "XIAO-IMU" over BLE using the Nordic UART Service (NUS).
Reads ax,ay,az,gx,gy,gz at ~20 Hz via BLE notifications, extracts
features over a 20-frame sliding window, and classifies motion state.

Highlights state transitions so you can verify accuracy by moving the board.

Known issue: bleak's WinRT backend on Windows may establish a BLE
connection but fail to receive notifications (CCCD write silently fails).
Use serial_state.py via USB for reliable wired operation.
"""

import asyncio
import time
import threading
from bleak import BleakClient, BleakScanner
from feature_extractor import FeatureExtractor
from state_classifier import StateClassifier

NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

latest_data = None
_buffer = b""
fe = FeatureExtractor()
sc = StateClassifier()
last_processed_data = None
last_state = None
state_start_time = None
frame_count = 0


def parse_line(line):
    text = line.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    parts = text.split(",")
    if len(parts) != 6:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def state_changed(new_state):
    """Handle a state transition — print a highlighted banner."""
    global last_state, state_start_time
    now = time.time()
    if last_state is not None and state_start_time is not None:
        duration = now - state_start_time
        print(f"\n{'='*60}")
        print(f"  STATE CHANGE: {last_state} -> {new_state}  (lasted {duration:.1f}s)")
        print(f"{'='*60}")
    else:
        print(f"\n  Initial state: {new_state}")
    last_state = new_state
    state_start_time = now


async def start_ble():
    global latest_data, _buffer

    devices = await BleakScanner.discover(timeout=5.0)
    target = None
    for d in devices:
        if d.name == "XIAO-IMU":
            target = d
            break

    if not target:
        print("XIAO-IMU not found")
        return

    print(f"Found: {target.name}  [{target.address}]")
    await asyncio.sleep(1)

    for attempt in range(3):
        try:
            print(f"Connecting (attempt {attempt+1}) ...")
            async with BleakClient(target.address, timeout=10.0) as client:
                print(f"Connected OK  (mtu={client.mtu_size})")

                def callback(sender, data):
                    global latest_data, _buffer
                    _buffer += data
                    while b"\n" in _buffer:
                        line, _buffer = _buffer.split(b"\n", 1)
                        result = parse_line(line)
                        if result is not None:
                            latest_data = result

                await client.start_notify(NUS_TX_UUID, callback)
                print(f"Receiving data... (notify {NUS_TX_UUID})")

                last_data_time = time.time()
                while client.is_connected:
                    if latest_data is not None:
                        last_data_time = time.time()
                    elif time.time() - last_data_time > 5:
                        print("Connected, but no IMU notifications received yet")
                        last_data_time = time.time()
                    await asyncio.sleep(0.05)

            print("Disconnected")
            return
        except Exception as e:
            print(f"Connection error: {e}")
            await asyncio.sleep(1)

    print("All connection attempts failed")


def ble_thread():
    asyncio.run(start_ble())


# ── Main thread ───────────────────────────────────
threading.Thread(target=ble_thread, daemon=True).start()

print("System started...\n")

while True:
    data = latest_data
    if data is not None and data != last_processed_data:
        last_processed_data = data
        features = fe.update(data)
        ax, ay, az, gx, gy, gz = data
        frame_count += 1

        if len(fe.window) < 20:
            continue   # warming up, don't classify yet

        state = sc.classify(features)

        if state != last_state:
            state_changed(state)

        # Compact status every second (~20 frames)
        if frame_count % 20 == 0:
            elapsed = time.time() - state_start_time if state_start_time else 0
            print(f"  [{state:<10}] {elapsed:5.1f}s  |  "
                  f"az={az:+6.3f}  acc_var={features['acc_var']:.4f}  "
                  f"gyro_mag={features['gyro_mag']:.4f}")

    time.sleep(0.05)
