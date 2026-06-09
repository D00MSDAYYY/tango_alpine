from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from conf._conf import _Configurator


class AnomalyDetectorConfigurator(_Configurator):
    z_score_enabled_changed = Signal(bool)
    z_score_threshold_changed = Signal(float)
    z_score_window_size_changed = Signal(int)
    z_score_min_points_changed = Signal(int)
    delta_jump_enabled_changed = Signal(bool)
    delta_jump_threshold_changed = Signal(float)
    delta_jump_min_points_changed = Signal(int)

    def __init__(self, sett):
        super().__init__(sett=sett)

    def _setup_ui(self):  # type: ignore
        layout = QVBoxLayout(self)
        warning_label = QLabel(
            "Предупреждение: включение стратегий обнаружения аномалий "
            "может заметно замедлить обновление графика на больших объемах данных."
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        form = QFormLayout()
        self.form = form

        z_score_check = QCheckBox()
        self.z_score_check = z_score_check
        z_score_check.setChecked(self.sett.anomaly_z_score_enabled)
        z_score_check.toggled.connect(self._on_z_score_enabled_changed)
        form.addRow("Z-score:", z_score_check)

        z_score_threshold_spin = QDoubleSpinBox()
        self.z_score_threshold_spin = z_score_threshold_spin
        z_score_threshold_spin.setRange(0.1, 1000.0)
        z_score_threshold_spin.setDecimals(2)
        z_score_threshold_spin.setSingleStep(0.1)
        z_score_threshold_spin.setValue(self.sett.anomaly_z_score_threshold)
        z_score_threshold_spin.valueChanged.connect(
            self._on_z_score_threshold_changed
        )
        form.addRow("Z-score порог:", z_score_threshold_spin)

        z_score_window_size_spin = QSpinBox()
        self.z_score_window_size_spin = z_score_window_size_spin
        z_score_window_size_spin.setRange(2, 1_000_000)
        z_score_window_size_spin.setValue(self.sett.anomaly_z_score_window_size)
        z_score_window_size_spin.valueChanged.connect(
            self._on_z_score_window_size_changed
        )
        form.addRow("Z-score окно, точек:", z_score_window_size_spin)

        z_score_min_points_spin = QSpinBox()
        self.z_score_min_points_spin = z_score_min_points_spin
        z_score_min_points_spin.setRange(2, 1_000_000)
        z_score_min_points_spin.setValue(self.sett.anomaly_z_score_min_points)
        z_score_min_points_spin.valueChanged.connect(
            self._on_z_score_min_points_changed
        )
        form.addRow("Z-score минимум, точек:", z_score_min_points_spin)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        form.addRow(separator)

        delta_jump_check = QCheckBox()
        self.delta_jump_check = delta_jump_check
        delta_jump_check.setChecked(self.sett.anomaly_delta_jump_enabled)
        delta_jump_check.toggled.connect(self._on_delta_jump_enabled_changed)
        form.addRow("Резкий скачок:", delta_jump_check)

        delta_jump_threshold_spin = QDoubleSpinBox()
        self.delta_jump_threshold_spin = delta_jump_threshold_spin
        delta_jump_threshold_spin.setRange(0.0, 1_000_000_000.0)
        delta_jump_threshold_spin.setDecimals(3)
        delta_jump_threshold_spin.setSingleStep(0.1)
        delta_jump_threshold_spin.setValue(self.sett.anomaly_delta_jump_threshold)
        delta_jump_threshold_spin.valueChanged.connect(
            self._on_delta_jump_threshold_changed
        )
        form.addRow("Скачок порог:", delta_jump_threshold_spin)

        delta_jump_min_points_spin = QSpinBox()
        self.delta_jump_min_points_spin = delta_jump_min_points_spin
        delta_jump_min_points_spin.setRange(2, 1_000_000)
        delta_jump_min_points_spin.setValue(self.sett.anomaly_delta_jump_min_points)
        delta_jump_min_points_spin.valueChanged.connect(
            self._on_delta_jump_min_points_changed
        )
        form.addRow("Скачок минимум, точек:", delta_jump_min_points_spin)

        layout.addLayout(form)
        self._set_z_score_params_enabled(self.sett.anomaly_z_score_enabled)
        self._set_delta_jump_params_enabled(self.sett.anomaly_delta_jump_enabled)

    def _on_z_score_enabled_changed(self, checked: bool):
        self.pending_settings.anomaly_z_score_enabled = checked
        self._set_z_score_params_enabled(checked)
        self.z_score_enabled_changed.emit(checked)

    def _on_z_score_threshold_changed(self, threshold: float):
        self.pending_settings.anomaly_z_score_threshold = float(threshold)
        self.z_score_threshold_changed.emit(float(threshold))

    def _on_z_score_window_size_changed(self, value: int):
        self.pending_settings.anomaly_z_score_window_size = int(value)
        self.z_score_window_size_changed.emit(int(value))

    def _on_z_score_min_points_changed(self, value: int):
        self.pending_settings.anomaly_z_score_min_points = int(value)
        self.z_score_min_points_changed.emit(int(value))

    def _on_delta_jump_enabled_changed(self, checked: bool):
        self.pending_settings.anomaly_delta_jump_enabled = checked
        self._set_delta_jump_params_enabled(checked)
        self.delta_jump_enabled_changed.emit(checked)

    def _on_delta_jump_threshold_changed(self, threshold: float):
        self.pending_settings.anomaly_delta_jump_threshold = float(threshold)
        self.delta_jump_threshold_changed.emit(float(threshold))

    def _on_delta_jump_min_points_changed(self, value: int):
        self.pending_settings.anomaly_delta_jump_min_points = int(value)
        self.delta_jump_min_points_changed.emit(int(value))

    def _set_z_score_params_enabled(self, enabled: bool):
        self.z_score_threshold_spin.setEnabled(enabled)
        self.z_score_window_size_spin.setEnabled(enabled)
        self.z_score_min_points_spin.setEnabled(enabled)

    def _set_delta_jump_params_enabled(self, enabled: bool):
        self.delta_jump_threshold_spin.setEnabled(enabled)
        self.delta_jump_min_points_spin.setEnabled(enabled)
