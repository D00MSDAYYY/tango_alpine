from typing import Protocol


class _PlotCurve(Protocol):
    def set_data(self, data, refresh: bool = True) -> None:
        ...

    def set_style(self, color=None, width=None, show_dots=None) -> None:
        ...


class _PlotWidget(Protocol):
    def set_time_range(self, value: float) -> None:
        ...

    def set_history_range(self, value: float) -> None:
        ...

    def set_max_plot_points(self, value: int) -> None:
        ...

    def set_axis_labels(self, x_label: str, y_label: str) -> None:
        ...

    def set_x_axis_label(self, label: str) -> None:
        ...

    def set_y_axis_label(self, label: str) -> None:
        ...

    def set_paused(self, paused: bool, time_reference=None) -> None:
        ...

    def add_curve(self, pen) -> _PlotCurve:
        ...

    def remove_curve(self, curve: _PlotCurve) -> None:
        ...

    def refresh(self) -> None:
        ...


class _PlotCurveFactory(Protocol):
    def create_curve(self, cnl) -> _PlotCurve:
        ...

    def update_curve_style(self, cnl, curve: _PlotCurve) -> None:
        ...
