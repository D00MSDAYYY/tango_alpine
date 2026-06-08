from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from aux.anomaly._strategy import (
    AnomalyStrategy,
    StrategyDetectionResult,
)


class AnomalyDetector:
    def __init__(
        self,
        strategies: Mapping[str, AnomalyStrategy] | None = None,
    ):
        self.strategies = dict(strategies or {})

    def add_strategy(
        self,
        strategy_name: str,
        strategy: AnomalyStrategy,
    ):
        self.strategies[strategy_name] = strategy

    def remove_strategy(self, strategy_name: str):
        self.strategies.pop(strategy_name, None)

    def detect(
        self,
        data: np.ndarray | Sequence[Mapping[str, Any]],
    ) -> tuple[StrategyDetectionResult, ...]:
        points = self._to_points(data)
        return tuple(
            strategy.detect(points)
            for strategy in tuple(self.strategies.values())
        )

    def _to_points(self, data: np.ndarray | Sequence[Mapping[str, Any]]) -> np.ndarray:
        if isinstance(data, np.ndarray):
            points = np.asarray(data, dtype=np.float64)
            if points.size == 0:
                return np.empty((0, 2), dtype=np.float64)
            return points.reshape((-1, 2))

        points = []
        for record in data:
            try:
                points.append((float(record["timestamp"]), float(record["value"])))
            except (KeyError, TypeError, ValueError):
                continue
        if not points:
            return np.empty((0, 2), dtype=np.float64)
        return np.asarray(points, dtype=np.float64)
