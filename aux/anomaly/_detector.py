from typing import Protocol


class _AnomalyDetector(Protocol):
    def configure(self, value=None) -> None:
        ...

    def add_cnl(self, cnl) -> None:
        ...

    def remove_cnl(self, cnl) -> None:
        ...

    def detect(self, cnl, data) -> None:
        ...
