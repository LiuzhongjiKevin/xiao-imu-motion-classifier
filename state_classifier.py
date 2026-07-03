class StateClassifier:

    def __init__(self):
        self.state = "unknown"

    def classify(self, f):
        acc_var = f["acc_var"]
        gyro = f["gyro_mag"]
        ax, ay, az, _, _, _ = f["raw"]

        # 静止
        if acc_var < 0.01:
            if abs(az - 1) < 0.2:
                return "standing"
            elif abs(az + 1) < 0.2:
                return "lying"
            else:
                return "sitting"

        # 运动
        else:
            if acc_var < 0.05:
                return "walking"
            elif acc_var < 0.15:
                return "running"
            else:
                return "jumping"