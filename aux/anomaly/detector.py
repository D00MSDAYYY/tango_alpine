from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, Qt

from aux.anomaly._strategy import (
    AnomalyStrategy,
    StrategyDetectionResult,
)
from aux.anomaly._runner import _AnomalyDetectionRunner
from aux.anomaly.runner import (
    NoOpAnomalyDetectionRunner,
    ThreadedAnomalyDetectionRunner,
)
from aux.anomaly.strategies import DeltaJumpStrategy, ZScoreStrategy


class _StrategyDetector:
    def __init__(self, strategies: Mapping[str, AnomalyStrategy]):
        self.strategies = dict(strategies)

    def detect_points(
        self,
        points: np.ndarray,
    ) -> tuple[StrategyDetectionResult, ...]:
        return tuple(
            strategy.detect(points)
            for strategy in tuple(self.strategies.values())
        )


class AnomalyDetector(QObject):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.cnls = set()
        self.versions = {}
        self.runner: _AnomalyDetectionRunner | None = None
        self.strategies: dict[str, AnomalyStrategy] = {}
        self.configure()

    def configure(self, value=None):
        for cnl in self.cnls:
            self.versions[cnl] = self.versions.get(cnl, 0) + 1

        self.strategies = self._make_strategies()
        if self.strategies:
            self.runner = ThreadedAnomalyDetectionRunner(
                _StrategyDetector(self.strategies),
                parent=self,
            )
        else:
            self.runner = NoOpAnomalyDetectionRunner(parent=self)

        self.runner.completed.connect(
            self._on_detection_finished,
            Qt.ConnectionType.QueuedConnection,
        )

        if not self.strategies:
            for cnl in self.cnls:
                cnl.set_anomaly_results(())

    def add_cnl(self, cnl):
        self.cnls.add(cnl)
        self.versions.setdefault(cnl, 0)

    def remove_cnl(self, cnl):
        self.cnls.discard(cnl)
        self.versions.pop(cnl, None)

    def detect(self, cnl, data: np.ndarray | Sequence[Mapping[str, Any]]):
        if cnl not in self.cnls or self.runner is None:
            return

        version = self.versions.get(cnl, 0) + 1
        points = self._to_points(data)
        if self.runner.detect(cnl, points, version):
            self.versions[cnl] = version

    def detect_points(
        self,
        points: np.ndarray,
    ) -> tuple[StrategyDetectionResult, ...]:
        return _StrategyDetector(self.strategies).detect_points(points)

    def _on_detection_finished(self, cnl, version, strategy_results):
        if cnl not in self.cnls:
            return
        if self.versions.get(cnl) != version:
            return
        cnl.set_anomaly_results(strategy_results)

    def _make_strategies(self) -> dict[str, AnomalyStrategy]:
        strategies = {}
        if self.settings.anomaly_z_score_enabled:
            strategies["z_score"] = ZScoreStrategy(
                threshold=self.settings.anomaly_z_score_threshold,
                window_size=self.settings.anomaly_z_score_window_size,
                min_points=self.settings.anomaly_z_score_min_points,
            )
        if self.settings.anomaly_delta_jump_enabled:
            strategies["delta_jump"] = DeltaJumpStrategy(
                threshold=self.settings.anomaly_delta_jump_threshold,
                min_points=self.settings.anomaly_delta_jump_min_points,
            )
        return strategies

    def set_strategies(
        self,
        strategies: Mapping[str, AnomalyStrategy],
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

    def detect_data(
        self,
        data: np.ndarray | Sequence[Mapping[str, Any]],
    ) -> tuple[StrategyDetectionResult, ...]:
        points = self._to_points(data)
        return self.detect_points(points)

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
