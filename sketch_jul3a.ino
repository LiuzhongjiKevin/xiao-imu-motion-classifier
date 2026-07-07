#include <Arduino.h>
#include <bluefruit.h>
#include "LSM6DS3.h"
#include "Wire.h"

LSM6DS3 imu(I2C_MODE, 0x6A);
BLEUart bleuart;

void setup() {
  Serial.begin(115200);
  delay(1000);

  if (imu.begin() != 0) {
    Serial.println("IMU init failed!");
    while (1);
  }
  Serial.println("IMU ready");

  Bluefruit.begin();
  Bluefruit.setName("XIAO-IMU");
  Bluefruit.setTxPower(4);

  bleuart.begin();
  bleuart.bufferTXD(true);

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("READY");
}

void loop() {
  float ax = imu.readFloatAccelX();
  float ay = imu.readFloatAccelY();
  float az = imu.readFloatAccelZ();
  float gx = imu.readFloatGyroX();
  float gy = imu.readFloatGyroY();
  float gz = imu.readFloatGyroZ();

  // Always output to Serial for wired debugging
  Serial.print(ax, 3); Serial.print(",");
  Serial.print(ay, 3); Serial.print(",");
  Serial.print(az, 3); Serial.print(",");
  Serial.print(gx, 3); Serial.print(",");
  Serial.print(gy, 3); Serial.print(",");
  Serial.println(gz, 3);

  // Also send over BLE if connected
  if (Bluefruit.connected()) {
    String data = String(ax, 3) + "," + String(ay, 3) + "," + String(az, 3) + "," +
                  String(gx, 3) + "," + String(gy, 3) + "," + String(gz, 3) + "\n";
    size_t written = bleuart.write(data.c_str(), data.length());
    bleuart.flushTXD();

    if (written == 0) {
      Serial.println("BLE notify not enabled or write failed");
    }
  }

  delay(50);
}
