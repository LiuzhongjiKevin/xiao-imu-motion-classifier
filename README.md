# XIAO IMU Motion State Classifier

Seeed XIAO nRF52840 Sense 的 IMU 数据采集与运动状态识别系统。通过 LSM6DS3 六轴传感器实时采集加速度+陀螺仪数据，基于滑动窗口特征提取 + 规则分类器，检测并输出当前运动状态，同时监控状态转换。

## 硬件

| 组件 | 型号 |
|------|------|
| 开发板 | Seeed XIAO nRF52840 Sense |
| IMU | LSM6DS3（I2C，地址 0x6A） |
| 无线 | nRF52840 BLE 5.0 |
| MCU | ARM Cortex-M4F @ 64 MHz |

## 技术架构

```
┌─────────────────────────────────────────────────┐
│              XIAO nRF52840 Sense                 │
│                                                  │
│   LSM6DS3 ──I2C──► MCU                          │
│                     │                            │
│          ┌──────────┴──────────┐                 │
│          │  sketch_jul3a.ino   │                 │
│          │  20 Hz data loop    │                 │
│          └──────────┬──────────┘                 │
│                     │                            │
│        ┌────────────┼────────────┐               │
│        │            │            │               │
│    Serial(USB)   BLE NUS      (debug)           │
│    COM5/auto     TX notify    Serial.print      │
│        │            │                            │
└────────┼────────────┼────────────────────────────┘
         │            │
         ▼            ▼
   ┌──────────┐  ┌──────────┐
   │serial_    │  │main.py   │
   │state.py   │  │(bleak)   │
   │✅ 已验证  │  │❌ WinRT  │
   │可靠运行   │  │兼容问题  │
   └─────┬─────┘  └──────────┘
         │
         ▼
   ┌─────────────────────┐
   │  FeatureExtractor    │
   │  - 20 帧滑动窗口     │
   │  - acc_mag 合成加速度│
   │  - gyro_mag 合成角速度│
   │  - acc_var 加速度方差 │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │   StateClassifier    │
   │   规则分类器          │
   │   6 种运动状态        │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  State Change        │
   │  Monitor             │
   │  检测状态转换         │
   │  记录持续时间         │
   └─────────────────────┘
```

## 数据协议

**Nordic UART Service (NUS)**

| 角色 | UUID |
|------|------|
| Service | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` |
| TX（XIAO→Central, notify） | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` |
| RX（Central→XIAO, write） | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` |

**数据格式**（每条一行，~20 Hz）：

```
ax,ay,az,gx,gy,gz
0.012,0.003,1.021,-0.001,0.002,0.001
```

## 运动状态分类规则

20 帧（~1 秒）滑动窗口计算加速度方差 `acc_var`，结合当前 Z 轴加速度判断姿态：

| 状态 | 条件 | 典型场景 |
|------|------|----------|
| `standing` | `acc_var < 0.01` 且 `az ≈ +1.0g` | 直立静止 |
| `lying` | `acc_var < 0.01` 且 `az ≈ -1.0g` | 平躺 |
| `sitting` | `acc_var < 0.01` 且其他朝向 | 静坐/侧卧 |
| `walking` | `0.01 ≤ acc_var < 0.05` | 步行 |
| `running` | `0.05 ≤ acc_var < 0.15` | 跑步 |
| `jumping` | `acc_var ≥ 0.15` | 跳跃/剧烈运动 |

> 阈值可根据实际传感器噪声微调，定义在 `state_classifier.py` 中。

## 状态转换监测

两个 Python 脚本均包含状态转换检测：

```
============================================================
  STATE CHANGE: standing -> walking  (lasted 12.3s)
============================================================
  [walking   ]   5.2s  |  az=+0.987  acc_var=0.0234  gyro_mag=0.1245
```

- **状态变化时**：打印醒目的 banner，显示旧状态→新状态及持续时间
- **每秒 1 次**：打印当前状态的紧凑状态行
- **预热阶段**：前 20 帧（~1 秒）不出结果，待滑动窗口填满

### 如何验证准确性

1. 上传 `sketch_jul3a.ino` 到 XIAO
2. 运行 `python serial_state.py`
3. 按顺序做以下动作，观察状态输出：

| 动作 | 期望输出 |
|------|----------|
| 板子平放桌面不动 | `standing`（az≈+1.0） |
| 板子翻转背面朝上 | `lying`（az≈-1.0） |
| 板子侧立 | `sitting` |
| 手持板子慢走 | `walking` |
| 手持板子快跑 | `running` |
| 手持板子跳跃 | `jumping` |

## 文件说明

| 文件 | 用途 |
|------|------|
| `sketch_jul3a.ino` | Arduino 固件 — IMU → Serial + BLE 双通道输出，20 Hz |
| `serial_state.py` | **有线版** — 串口读取 + 特征提取 + 状态分类 + 转换监测 ✅ |
| `main.py` | **蓝牙版** — BLE 接收 + 特征提取 + 状态分类 + 转换监测 ⚠️ |
| `feature_extractor.py` | 滑动窗口特征提取（`acc_mag`, `gyro_mag`, `acc_var`） |
| `state_classifier.py` | 6 状态规则分类器 |
| `imu_ble_receiver.py` | 早期 BLE 接收端代码（已废弃，保留作为参考） |

## 已知问题

### ❌ BLE 连接成功但无 notify 数据（Windows）

**现象**：
- `main.py` 能扫描到 `XIAO-IMU`，MTU=23 连接成功
- `start_notify()` 调用无异常
- 但回调从不触发，无任何数据到达
- 同时 Arduino IDE 串口监视器显示数据正常输出

**已排查**：
- ✅ UUID 匹配（`6E400003` NUS TX）
- ✅ Arduino 端 BLEUart `bufferTXD(true)` + `flushTXD()` 已启用
- ✅ 有 `written == 0` 检测（缓冲模式下始终返回 0，不说明问题）
- ✅ 有线 `serial_state.py` 数据流正常
- ✅ 服务发现能找到 TX characteristic，属性含 `notify`

**推测根因**：
bleak（WinRT 后端）在 Windows 上对 CCCD descriptor 的写入可能静默失败，导致 notification 从未真正启用。MTU=23 也可能表明连接协商异常（nRF52840 标准支持 247）。

**尝试过的修复**：
- 跳过 service discovery，直接用 UUID 字符串订阅
- 手动写 CCCD descriptor `\x01\x00`
- 扫描后延迟 1s 再连接
- 多线程 / 单线程 asyncio 架构切换
- 以上方法均未解决

**替代方案**：使用 `serial_state.py` 有线 USB 串口模式，数据通路确认可靠。

### ⚠️ ArduinoBLE 库不兼容

XIAO nRF52840 使用 mbed OS 内核，不支持标准 `ArduinoBLE.h`。链接阶段报错：
```
undefined reference to `HCITransport'
```

**解决方案**：使用板子包内置的 `Bluefruit52Lib`（`#include <bluefruit.h>`）。

## 使用方法

### 有线模式（推荐，已验证 ✅）

```bash
# 1. Arduino IDE 打开 sketch_jul3a.ino
# 2. 选择 Tools → Board → Seeed XIAO nRF52840 Sense
# 3. 编译上传到 XIAO
# 4. 关闭 Arduino IDE 串口监视器（释放 COM 口）
# 5. 运行
python serial_state.py
```

### 无线模式（Windows 下可能无数据 ⚠️）

```bash
python main.py
```

## 依赖

**Arduino 库**（通过 Board Manager 自动安装）：
- Seeed nRF52 Boards（含 Bluefruit52Lib）
- LSM6DS3

**Python 包**：
```bash
pip install bleak pyserial
```

## License

MIT
