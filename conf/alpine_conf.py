from datetime import timedelta

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)
from conf._conf import _Configurator


class AlpineConfigurator(_Configurator):
    to_datetime_changed = Signal(object)
    time_range_changed = Signal(timedelta)
    history_range_changed = Signal(timedelta)
    max_redraw_hz_changed = Signal(float)
    max_plot_points_changed = Signal(int)
    x_label_changed = Signal(str)
    y_label_changed = Signal(str)  # TODO mb remove all

    def __init__(self, sett):
        super().__init__(sett=sett)

    def _setup_ui(self):  # type: ignore
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.form = form

        # Интервал
        time_range_spin = QSpinBox()
        self.time_range_spin = time_range_spin
        time_range_spin.valueChanged.connect(self._on_time_range_changed)
        time_range_spin.setRange(1, 86400 * 365)
        time_range_spin.setValue(int(self.sett.time_range.total_seconds()))
        self.form.addRow("Интервал, сек:", time_range_spin)

        history_range_spin = QSpinBox()
        self.history_range_spin = history_range_spin
        history_range_spin.valueChanged.connect(self._on_history_range_changed)
        history_range_spin.setRange(0, 86400 * 365)
        history_range_spin.setValue(int(self.sett.history_range.total_seconds()))
        self.form.addRow("История, сек:", history_range_spin)

        max_redraw_hz_spin = QSpinBox()
        self.max_redraw_hz_spin = max_redraw_hz_spin
        max_redraw_hz_spin.valueChanged.connect(self._on_max_redraw_hz_changed)
        max_redraw_hz_spin.setRange(1, 240)
        max_redraw_hz_spin.setValue(int(round(self.sett.max_redraw_hz)))
        self.form.addRow("Макс. отрисовка, Hz:", max_redraw_hz_spin)

        max_plot_points_spin = QSpinBox()
        self.max_plot_points_spin = max_plot_points_spin
        max_plot_points_spin.valueChanged.connect(self._on_max_plot_points_changed)
        max_plot_points_spin.setRange(2, 10_000_000)
        max_plot_points_spin.setValue(int(self.sett.max_plot_points))
        self.form.addRow("Макс. точек на линию:", max_plot_points_spin)

        # Ось X
        x_label_edit = QLineEdit()
        self.x_label_edit = x_label_edit
        x_label_edit.textChanged.connect(self._on_x_label_changed)
        x_label_edit.setText(self.sett.x_axis_label)
        form.addRow("Ось X:", x_label_edit)
        self.x_label_edit = x_label_edit

        # Ось Y
        y_label_edit = QLineEdit()
        self.y_label_edit = y_label_edit
        y_label_edit.textChanged.connect(self._on_y_label_changed)
        y_label_edit.setText(self.sett.y_axis_label)
        form.addRow("Ось Y:", y_label_edit)
        self.y_label_edit = y_label_edit

        layout.addLayout(self.form)

    def _on_time_range_changed(self, seconds: int):
        td = timedelta(seconds=seconds)
        self.pending_settings.time_range = td
        self.time_range_changed.emit(td)

    def _on_history_range_changed(self, seconds: int):
        td = timedelta(seconds=seconds)
        self.pending_settings.history_range = td
        self.history_range_changed.emit(td)

    def _on_max_redraw_hz_changed(self, hz: int):
        self.pending_settings.max_redraw_hz = float(hz)
        self.max_redraw_hz_changed.emit(float(hz))

    def _on_max_plot_points_changed(self, value: int):
        self.pending_settings.max_plot_points = int(value)
        self.max_plot_points_changed.emit(int(value))

    def _on_x_label_changed(self, label: str):
        self.pending_settings.x_axis_label = label
        self.x_label_changed.emit(label)

    def _on_y_label_changed(self, label: str):
        self.pending_settings.y_axis_label = label
        self.y_label_changed.emit(label)
