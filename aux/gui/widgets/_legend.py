from typing import Protocol


class _Legend(Protocol):
    def add_cnl(self, cnl) -> None:
        ...

    def remove_cnl(self, cnl) -> None:
        ...

    def clear(self) -> None:
        ...

    def get_channels(self) -> list:
        ...

    def minimumWidth(self) -> int:
        ...
