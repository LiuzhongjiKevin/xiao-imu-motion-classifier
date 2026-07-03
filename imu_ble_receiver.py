import asyncio
from bleak import BleakClient, BleakScanner

# Nordic UART Service (NUS) TX characteristic
CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

latest_data = None
_buffer = b""

def parse(data):
    text = data.decode().strip()
    if not text:
        return None
    parts = text.split(",")
    if len(parts) != 6:
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    return vals

async def start_ble():
    global latest_data

    devices = await BleakScanner.discover()

    target = None
    for d in devices:
        if d.name == "XIAO-IMU":
            target = d
            break

    if not target:
        print("XIAO-IMU not found")
        return

    print("Found:", target.name, target.address)
    await asyncio.sleep(1)  # let BLE stack settle

    for attempt in range(3):
        try:
            print(f"Connecting (attempt {attempt+1})...")
            async with BleakClient(target.address, timeout=10.0) as client:
                print("Connected OK")

                # Discover services and find NUS TXD
                txd_uuid = None
                for svc in client.services:
                    for char in svc.characteristics:
                        print(f"  {char.uuid} | notify={char.properties}")
                        if "6e400003" in str(char.uuid).lower():
                            txd_uuid = char.uuid
                            print(f"  >>> FOUND NUS TXD: {txd_uuid}")

                if not txd_uuid:
                    print("NUS TXD characteristic not found!")
                    break

                def callback(sender, data):
                    global latest_data, _buffer
                    _buffer += data
                    while b"\n" in _buffer:
                        line, _buffer = _buffer.split(b"\n", 1)
                        result = parse(line)
                        if result:
                            latest_data = result

                await client.start_notify(txd_uuid, callback)
                print("Receiving data...")

                while client.is_connected:
                    await asyncio.sleep(0.05)

            print("Disconnected")
            break
        except Exception as e:
            print(f"Connection failed: {e}")
            await asyncio.sleep(1)
    else:
        print("All connection attempts failed")