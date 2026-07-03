import math

class FeatureExtractor:
    def __init__(self):
        self.window = []

    def update(self, data):
        ax, ay, az, gx, gy, gz = data

        acc_mag = math.sqrt(ax*ax + ay*ay + az*az)
        gyro_mag = math.sqrt(gx*gx + gy*gy + gz*gz)

        self.window.append(acc_mag)

        if len(self.window) > 20:
            self.window.pop(0)

        acc_var = sum((x - sum(self.window)/len(self.window))**2 for x in self.window) / len(self.window)

        return {
            "acc_mag": acc_mag,
            "gyro_mag": gyro_mag,
            "acc_var": acc_var,
            "raw": data
        }