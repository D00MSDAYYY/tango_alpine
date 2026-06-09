from typing import Protocol

from PySide6.QtCore import QObject

from aux.anomaly._detector import _AnomalyDetector


class _AnomalyDetectorFactory(Protocol):
    def create(self, settings, parent: QObject | None = None) -> _AnomalyDetector:
        ...
