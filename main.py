import asyncio
import time
import threading
from bleak import BleakClient, BleakScanner

CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

latest_data = None
_buffer = b""

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

                await client.start_notify(CHAR_UUID, callback)
                print("Receiving data...")

                while client.is_connected:
                    await asyncio.sleep(0.05)

            print("Disconnected")
            return
        except Exception as e:
            print(f"Connection error: {e}")
            await asyncio.sleep(1)

    print("All connection attempts failed")

def ble_thread():
    asyncio.run(start_ble())

threading.Thread(target=ble_thread, daemon=True).start()

print("System started...\n")

while True:
    data = latest_data
    if data is not None:
        ax, ay, az, gx, gy, gz = data
        print(f"IMU | ax={ax:+7.3f} ay={ay:+7.3f} az={az:+7.3f} | gx={gx:+7.3f} gy={gy:+7.3f} gz={gz:+7.3f}")
    time.sleep(0.05)
