from typing import Protocol


class _ChannelProtocol(Protocol):
    settings: object
    data: list

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def create_plot_curve(self, plot_curve_factory):
        ...

    def set_anomaly_results(self, strategy_results) -> None:
        ...
