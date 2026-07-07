"""Serial IMU receiver + real-time motion state classifier.

Connects to XIAO nRF52840 Sense over USB serial (COM port auto-detect).
Reads ax,ay,az,gx,gy,gz at ~20 Hz, extracts features over a 20-frame
sliding window, and classifies the current motion state.

Highlights state transitions so you can verify accuracy by moving the board.
"""

import serial
import time
from serial.tools import list_ports
from feature_extractor import FeatureExtractor
from state_classifier import StateClassifier

PORT = "COM5"
BAUD = 115200

fe = FeatureExtractor()
sc = StateClassifier()

last_state = None
state_start_time = None
frame_count = 0


def pick_port():
    """Auto-detect the XIAO COM port by scanning USB descriptors."""
    candidates = []
    for port in list_ports.comports():
        desc = f"{port.description} {port.manufacturer or ''} {port.hwid or ''}".lower()
        if any(key in desc for key in ("xiao", "nrf52840", "arduino", "usb serial", "cdc")):
            candidates.append(port.device)
    if candidates:
        return candidates[0]
    return PORT


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


# ── Main ──────────────────────────────────────────
PORT = pick_port()
print(f"Opening {PORT} at {BAUD} baud ...")

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(1)
ser.reset_input_buffer()   # drain boot messages

print("Waiting for IMU data...")
print("Move the board to test state detection.\n")

while True:
    try:
        line = ser.readline().decode("utf-8", errors="replace").strip()
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        break

    if not line:
        continue

    parts = line.split(",")
    if len(parts) != 6:
        continue   # skip "IMU ready", "READY", etc.

    try:
        vals = [float(p) for p in parts]
    except ValueError:
        continue

    ax, ay, az, gx, gy, gz = vals
    frame_count += 1

    features = fe.update(vals)

    # Warmup: need 20 frames to fill the sliding window
    if len(fe.window) < 20:
        continue

    state = sc.classify(features)

    if state != last_state:
        state_changed(state)

    # Print a compact status line every second (every ~20 frames)
    if frame_count % 20 == 0:
        elapsed = time.time() - state_start_time if state_start_time else 0
        print(f"  [{state:<10}] {elapsed:5.1f}s  |  "
              f"az={az:+6.3f}  acc_var={features['acc_var']:.4f}  "
              f"gyro_mag={features['gyro_mag']:.4f}")
