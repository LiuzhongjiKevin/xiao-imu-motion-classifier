import serial
import time
from feature_extractor import FeatureExtractor
from state_classifier import StateClassifier

PORT = "COM5"
BAUD = 115200

fe = FeatureExtractor()
sc = StateClassifier()

print(f"Opening {PORT} at {BAUD} baud ...")

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(1)

# Drain setup messages
ser.reset_input_buffer()

print("Waiting for data...\n")

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
        continue  # skip setup messages like "IMU ready", "READY"

    try:
        vals = [float(p) for p in parts]
    except ValueError:
        continue

    ax, ay, az, gx, gy, gz = vals

    features = fe.update(vals)
    if len(fe.window) >= 20:
        state = sc.classify(features)
        print(f"STATE: {state:<10} | ax={ax:+7.3f} ay={ay:+7.3f} az={az:+7.3f} | "
              f"gx={gx:+7.3f} gy={gy:+7.3f} gz={gz:+7.3f} | "
              f"acc_var={features['acc_var']:.4f}")
