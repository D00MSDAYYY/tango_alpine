from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QSlider, QWidget


class NumericRangeSlider(QWidget):
    value_changed = Signal(float)
    bounds_changed = Signal(float, float)

    SLIDER_STEPS = 1000

    def __init__(
        self,
        minimum=0.0,
        maximum=100.0,
        value=None,
        parent=None,
    ):
        super().__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        if self._maximum <= self._minimum:
            self._maximum = self._minimum + 1.0
        self._value = self._clamp(
            float(value) if value is not None else self._minimum,
        )

        self._setup_ui()
        self._sync_controls()

    def value(self):
        return self._value

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def set_value(self, value):
        value = self._clamp(float(value))
        if value == self._value:
            self._sync_controls()
            return
        self._value = value
        self._sync_controls()
        self.value_changed.emit(self._value)

    def set_bounds(self, minimum, maximum):
        minimum = float(minimum)
        maximum = float(maximum)
        if maximum <= minimum:
            maximum = minimum + 1.0

        bounds_changed = minimum != self._minimum or maximum != self._maximum
        self._minimum = minimum
        self._maximum = maximum
        self._value = self._clamp(self._value)
        self._sync_controls()

        if bounds_changed:
            self.bounds_changed.emit(self._minimum, self._maximum)
            self.value_changed.emit(self._value)

    def _setup_ui(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        validator = QDoubleValidator(self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        validator.setBottom(0.0)

        minimum_edit = QLineEdit()
        self.minimum_edit = minimum_edit
        minimum_edit.setValidator(validator)
        minimum_edit.setFixedWidth(58)
        minimum_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        minimum_edit.setToolTip("Нижняя граница")
        minimum_edit.editingFinished.connect(self._on_bounds_edited)

        slider = QSlider(Qt.Orientation.Horizontal)
        self.slider = slider
        slider.setRange(0, self.SLIDER_STEPS)
        slider.setFixedWidth(180)
        slider.valueChanged.connect(self._on_slider_changed)

        maximum_edit = QLineEdit()
        self.maximum_edit = maximum_edit
        maximum_edit.setValidator(validator)
        maximum_edit.setFixedWidth(58)
        maximum_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        maximum_edit.setToolTip("Верхняя граница")
        maximum_edit.editingFinished.connect(self._on_bounds_edited)

        layout.addWidget(minimum_edit)
        layout.addWidget(slider)
        layout.addWidget(maximum_edit)

    def _on_bounds_edited(self):
        try:
            minimum = float(self.minimum_edit.text().replace(",", "."))
            maximum = float(self.maximum_edit.text().replace(",", "."))
        except ValueError:
            self._sync_controls()
            return
        self.set_bounds(minimum, maximum)

    def _on_slider_changed(self, slider_value):
        value = self._value_from_slider(slider_value)
        if value == self._value:
            return
        self._value = value
        self.slider.setToolTip(self._format_number(self._value))
        self.value_changed.emit(self._value)

    def _sync_controls(self):
        with QSignalBlocker(self.minimum_edit):
            self.minimum_edit.setText(self._format_number(self._minimum))
        with QSignalBlocker(self.maximum_edit):
            self.maximum_edit.setText(self._format_number(self._maximum))
        with QSignalBlocker(self.slider):
            self.slider.setValue(self._slider_from_value(self._value))
            self.slider.setToolTip(self._format_number(self._value))

    def _clamp(self, value):
        return min(max(value, self._minimum), self._maximum)

    def _slider_from_value(self, value):
        span = self._maximum - self._minimum
        if span <= 0:
            return 0
        ratio = (value - self._minimum) / span
        return round(ratio * self.SLIDER_STEPS)

    def _value_from_slider(self, slider_value):
        ratio = float(slider_value) / self.SLIDER_STEPS
        return self._minimum + ratio * (self._maximum - self._minimum)

    def _format_number(self, value):
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
