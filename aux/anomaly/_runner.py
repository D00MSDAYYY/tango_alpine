from typing import Protocol


class _AnomalyDetectionRunner(Protocol):
    def detect(self, cnl, points, version: int) -> bool:
        ...
