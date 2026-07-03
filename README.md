# XIAO IMU Motion State Classifier

Seeed XIAO nRF52840 Sense 的 IMU 数据采集与运动状态识别系统。通过 LSM6DS3 六轴传感器采集加速度+陀螺仪数据，实时分类人体运动状态。

## 硬件

| 组件 | 型号 |
|------|------|
| 开发板 | Seeed XIAO nRF52840 Sense |
| IMU | LSM6DS3（I2C，地址 0x6A） |
| 无线 | nRF52840 BLE 5.0 |
| MCU | ARM Cortex-M4F |

## 技术架构

```
                    ┌───────────────────────────┐
                    │   XIAO nRF52840 Sense      │
                    │                            │
                    │  LSM6DS3 ──I2C──► MCU     │
                    │                  │          │
                    │      ┌───────────┴──────┐  │
                    │      │ serial_state.py  │  │
                    │      │ (COM5, 115200)   │  │
                    │      └──────────────────┘  │
                    │      有线 ✅ 已验证可用     │
                    │                            │
                    │      ┌──────────────────┐  │
                    │      │ main.py           │  │
                    │      │ (BLE NUS)         │  │
                    │      └──────────────────┘  │
                    │      无线 ❌ 有兼容问题     │
                    └───────────────────────────┘
```

### 数据链路（有线模式，已确认可用）

```
LSM6DS3  ──I2C──► sketch_jul3a.ino ──Serial(115200)──► COM5 ──► serial_state.py ──► 状态输出
                                                                   │
                                                    ┌──────────────┴──────────────┐
                                                    │  FeatureExtractor            │
                                                    │  - 20 帧滑动窗口             │
                                                    │  - acc_mag, gyro_mag        │
                                                    │  - acc_var (加速度方差)      │
                                                    └──────────────┬──────────────┘
                                                                   │
                                                    ┌──────────────┴──────────────┐
                                                    │  StateClassifier             │
                                                    │  规则分类器（6种状态）        │
                                                    └──────────────┬──────────────┘
                                                                   │
                                           standing / lying / sitting / walking / running / jumping
```

### 数据链路（无线模式，存在问题）

```
LSM6DS3 ──► sketch_jul3a.ino ──BLEUart──► BLE NUS TX (6E400003) ──► main.py (bleak)
                                         ──► ❌ Connected OK 但无 notify 数据
```

### 协议

**Nordic UART Service (NUS)**

| 角色 | UUID |
|------|------|
| Service | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` |
| TX (XIAO→Central, notify) | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` |
| RX (Central→XIAO, write) | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` |

**数据格式**（每条一行，20Hz）：

```
ax,ay,az,gx,gy,gz
0.012,0.003,1.021,-0.001,0.002,0.001
```

## 文件说明

```
sketch_jul3a.ino      Arduino 固件 — BLE + Serial 双通道 IMU 数据输出
serial_state.py       有线串口接收 + 实时状态分类（✅ 可用）
main.py               BLE 接收端（❌ Windows BLE 栈兼容问题）
feature_extractor.py  滑动窗口特征提取
state_classifier.py   规则分类器
imu_ble_receiver.py   早期 BLE receiver（已废弃，功能合并进 main.py）
```

## 运动状态分类规则

| 状态 | 条件 |
|------|------|
| `standing` 站立 | `acc_var < 0.01` 且 `az ≈ 1.0g` |
| `lying` 躺卧 | `acc_var < 0.01` 且 `az ≈ -1.0g` |
| `sitting` 静坐 | `acc_var < 0.01` 且其他朝向 |
| `walking` 行走 | `0.01 ≤ acc_var < 0.05` |
| `running` 跑步 | `0.05 ≤ acc_var < 0.15` |
| `jumping` 跳跃 | `acc_var ≥ 0.15` |

> 分类参数根据实际传感器噪声水平可能需要微调。

## 已知问题

### ❌ BLE 连接成功但无 notify 数据

**现象**：
- Python（bleak WinRT 后端）扫描到 `XIAO-IMU` 并能建立连接
- `start_notify()` 调用不报错
- 但回调函数从不触发，无数据到达
- Arduino 串口监视器中数据正常输出

**已排查**：
- ✅ NUS TX characteristic UUID 正确（`6E400003`）
- ✅ Arduino 端 BLEUart 初始化正常
- ✅ 用 `nRF Connect` 手机 App 可连接并收到数据（待验证）
- ✅ 有线串口模式下数据流正常

**推测根因**：
- Windows 10/11 的 WinRT BLE 后端在 `bleak` 的 CCCD descriptor write 阶段可能静默失败，导致 notification 未能真正启用
- MTU 协商异常（实测 MTU 仅 23 bytes，nRF52840 标准应支持 247）
- 可能需要通过其他 BLE 库（如 `pygatt`、`winrt` 直接调用）或使用 WSL 下的 BlueZ 栈

**临时方案**：使用 `serial_state.py` 有线串口模式。

### ⚠️ ArduinoBLE 库不兼容

XIAO nRF52840 使用 mbed OS 内核，不支持标准 `ArduinoBLE.h`。链接阶段会报 `undefined reference to HCITransport`。

**解决方案**：使用板子内置的 `Bluefruit52Lib`（`#include <bluefruit.h>`），功能等价。

## 使用方法

### 有线模式（推荐）

```bash
# 1. Arduino IDE 上传 sketch_jul3a.ino 到 XIAO
# 2. 关闭 Arduino IDE 串口监视器
# 3. 运行
python serial_state.py
```

### 无线模式

```bash
# 确保 XIAO 已通电并运行固件
python main.py
```

## 依赖

**Arduino 库**（通过 Library Manager 安装）：
- Seeed nRF52 Boards（板子包，含 Bluefruit52Lib）
- LSM6DS3

**Python 包**：
```
pip install bleak pyserial
```

## License

MIT
