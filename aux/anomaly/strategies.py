import numpy as np

from aux.anomaly._strategy import Anomaly, StrategyDetectionResult


class NoAnomalyStrategy:
    def detect(self, points: np.ndarray) -> StrategyDetectionResult:
        return StrategyDetectionResult(strategy_name="none")


class DeltaJumpStrategy:
    def __init__(
        self,
        threshold: float = 20.0,
        min_points: int = 3,
    ):
        self.threshold = float(threshold)
        self.min_points = max(2, int(min_points))

    def detect(self, points: np.ndarray) -> StrategyDetectionResult:
        if len(points) < self.min_points:
            return StrategyDetectionResult(strategy_name="delta_jump")

        values = points[:, 1]
        deltas = np.abs(np.diff(values))
        if len(deltas) == 0:
            return StrategyDetectionResult(strategy_name="delta_jump")

        indexes = np.where(deltas >= self.threshold)[0] + 1
        anomalies = tuple(
            Anomaly(
                name="delta_jump",
                timestamp=float(points[index, 0]),
            )
            for index in indexes
        )

        return StrategyDetectionResult(
            strategy_name="delta_jump",
            anomalies=anomalies,
        )


class ZScoreStrategy:
    def __init__(
        self,
        threshold: float = 6.0,
        window_size: int = 300,
        min_points: int = 100,
    ):
        self.threshold = float(threshold)
        self.window_size = max(2, int(window_size))
        self.min_points = max(2, int(min_points))

    def detect(self, points: np.ndarray) -> StrategyDetectionResult:
        if len(points) < self.min_points:
            return StrategyDetectionResult(strategy_name="z_score")

        anomalies = []
        values = points[:, 1]

        for index in range(self.min_points, len(points)):
            window_start = max(0, index - self.window_size)
            window = values[window_start:index]
            mean = float(np.mean(window))
            std = float(np.std(window))
            value = float(values[index])
            if std == 0.0:
                if value == mean:
                    continue
                score = float("inf")
            else:
                score = abs((value - mean) / std)
            if score >= self.threshold:
                anomalies.append(
                    Anomaly(
                        name="z_score",
                        timestamp=float(points[index, 0]),
                    )
                )

        return StrategyDetectionResult(
            strategy_name="z_score",
            anomalies=tuple(anomalies),
        )
