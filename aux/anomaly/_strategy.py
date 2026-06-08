from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Anomaly:
    name: str
    timestamp: float


@dataclass(frozen=True)
class StrategyDetectionResult:
    strategy_name: str
    anomalies: tuple[Anomaly, ...] = ()

class AnomalyStrategy(Protocol):
    def detect(self, points: np.ndarray) -> StrategyDetectionResult: ...
