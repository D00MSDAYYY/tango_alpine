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

        values = points[:, 1]
        indexes = np.arange(self.min_points, len(points))
        window_starts = np.maximum(0, indexes - self.window_size)

        sums = np.concatenate(([0.0], np.cumsum(values)))
        squared_sums = np.concatenate(([0.0], np.cumsum(values * values)))
        counts = indexes - window_starts

        window_sums = sums[indexes] - sums[window_starts]
        window_squared_sums = squared_sums[indexes] - squared_sums[window_starts]
        means = window_sums / counts
        variances = np.maximum(window_squared_sums / counts - means * means, 0.0)
        stds = np.sqrt(variances)

        current_values = values[indexes]
        scores = np.zeros(len(indexes), dtype=np.float64)
        non_zero_std = stds > 0.0
        scores[non_zero_std] = np.abs(
            (current_values[non_zero_std] - means[non_zero_std])
            / stds[non_zero_std]
        )
        scores[~non_zero_std] = np.where(
            current_values[~non_zero_std] == means[~non_zero_std],
            0.0,
            np.inf,
        )

        anomaly_indexes = indexes[scores >= self.threshold]
        anomalies = tuple(
            Anomaly(
                name="z_score",
                timestamp=float(points[index, 0]),
            )
            for index in anomaly_indexes
        )

        return StrategyDetectionResult(
            strategy_name="z_score",
            anomalies=anomalies,
        )
