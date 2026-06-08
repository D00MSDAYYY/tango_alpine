from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
)

from conf._conf import _Configurator
from aux.gui.handy_enums import LineColor


class AppearenceConfigurator(_Configurator):
    line_color_changed = Signal(str)
    line_width_changed = Signal(float)
    show_dots_changed = Signal(bool)

    def __init__(self, sett):
        super().__init__(sett=sett)

    def _setup_ui(self):  # type: ignore
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.form = form
        layout.addLayout(form)

        # Цвет линии
        color_combo = QComboBox()
        self.color_combo = color_combo
        colors = [color.value for color in LineColor] # type: ignore
        color_combo.addItems(colors)
        color_combo.setCurrentText(self.sett.line_color.value)
        color_combo.currentTextChanged.connect(self._on_color_changed)
        form.addRow("Цвет линии:", color_combo)

        # Толщина линии
        width_spin = QDoubleSpinBox()
        self.width_spin = width_spin
        width_spin.setRange(0.5, 10.0)
        width_spin.setSingleStep(0.5)
        width_spin.setValue(self.sett.line_width)
        width_spin.valueChanged.connect(self._on_width_changed)
        form.addRow("Толщина линии:", width_spin)

        show_dots_check = QCheckBox()
        self.show_dots_check = show_dots_check
        show_dots_check.setChecked(self.sett.show_dots)
        show_dots_check.toggled.connect(self._on_show_dots_changed)
        form.addRow("Показывать точки:", show_dots_check)

    def _on_color_changed(self, color_str: str):
        new_color = LineColor(color_str) # type: ignore
        self.pending_settings.line_color = new_color
        self.line_color_changed.emit(color_str)

    def _on_width_changed(self, width: float):
        self.pending_settings.line_width = width
        self.line_width_changed.emit(width)

    def _on_show_dots_changed(self, show_dots: bool):
        self.pending_settings.show_dots = show_dots
        self.show_dots_changed.emit(show_dots)
