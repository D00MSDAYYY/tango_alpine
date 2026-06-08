from time import perf_counter
from collections import deque

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from vispy import app as vispy_app
from vispy import scene
from vispy.visuals.axis import Ticker

MAX_BACKGROUND_LINES = 24
POLL_INTERVAL_SEC = 0.05
MAX_HISTORY_SEC = 24 * 60 * 60
PREGENERATED_HISTORY_SEC = 200.0
PERIOD_LANE_HEIGHT = 3.0


class LaneValueTicker(Ticker):
    def _get_tick_frac_labels(self):
        major_frac, minor_frac, _ = super()._get_tick_frac_labels()
        domain_start, domain_end = self.axis.domain
        if len(major_frac) == 0:
            return major_frac, minor_frac, []
        values = domain_start + major_frac * (domain_end - domain_start)
        labels = [self._format_lane_value(value) for value in values]
        return major_frac, minor_frac, labels

    def _format_lane_value(self, value):
        lane_offset = np.floor((value + PERIOD_LANE_HEIGHT / 2.0) / PERIOD_LANE_HEIGHT)
        lane_offset = min(0.0, lane_offset * PERIOD_LANE_HEIGHT)
        return f"{value - lane_offset:.1f}"


class ElapsedTimeTicker(Ticker):
    def __init__(self, axis):
        super().__init__(axis)
        self.time_offset = 0.0

    def _get_tick_frac_labels(self):
        major_frac, minor_frac, _ = super()._get_tick_frac_labels()
        domain_start, domain_end = self.axis.domain
        if len(major_frac) == 0:
            return major_frac, minor_frac, []
        values = domain_start + major_frac * (domain_end - domain_start)
        labels = [
            self._format_elapsed_time(value + self.time_offset) for value in values
        ]
        return major_frac, minor_frac, labels

    def _format_elapsed_time(self, seconds):
        seconds = max(0, int(round(seconds)))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


class SignalGenerator:
    def __init__(self):
        self.rng = np.random.default_rng()
        self.next_spike_at = self._next_spike_delay()
        self.spikes = []

    def value(self, t):
        while t >= self.next_spike_at:
            amplitude = self.rng.uniform(0.7, 1.25)
            decay_sec = self.rng.uniform(0.35, 0.75)
            self.spikes.append((self.next_spike_at, amplitude, decay_sec))
            if self.rng.random() < 0.25:
                echo_delay = self.rng.uniform(0.35, 1.4)
                echo_amplitude = amplitude * self.rng.uniform(0.25, 0.55)
                self.spikes.append(
                    (self.next_spike_at + echo_delay, echo_amplitude, decay_sec)
                )
            self.next_spike_at += self._next_spike_delay()

        baseline = 0.45 + 0.02 * np.sin(t * 0.12)
        noise = 0.008 * self.rng.normal()
        value = baseline + noise

        alive_spikes = []
        for started_at, amplitude, decay_sec in self.spikes:
            age = t - started_at
            if age > 3.0:
                continue
            alive_spikes.append((started_at, amplitude, decay_sec))
            if age >= 0.0:
                value += amplitude * np.exp(-age / decay_sec)

        self.spikes = alive_spikes
        return value

    def _next_spike_delay(self):
        return float(np.clip(self.rng.exponential(5.0), 1.5, 12.0))


class HistoryPlot(QWidget):
    def __init__(self):
        super().__init__()

        self.period_sec = 20.0
        self.is_paused = False
        self.paused_now = None
        self.started_at = perf_counter() - PREGENERATED_HISTORY_SEC
        self.signal = SignalGenerator()
        self.samples = deque(maxlen=int(MAX_HISTORY_SEC / POLL_INTERVAL_SEC))
        self._pregenerate_history(PREGENERATED_HISTORY_SEC)

        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=True,
            bgcolor="#111111",
            size=(1100, 620),
            title="Vispy fixed-period history demo",
        )

        self.grid = self.canvas.central_widget.add_grid(spacing=0, margin=8)
        self.view = self.grid.add_view(row=0, col=1, camera="panzoom")
        self.view.camera.interactive = False

        self.y_axis = scene.AxisWidget(orientation="left")
        self.y_axis.axis.ticker = LaneValueTicker(self.y_axis.axis)
        self.x_axis = scene.AxisWidget(orientation="bottom")
        self.x_ticker = ElapsedTimeTicker(self.x_axis.axis)
        self.x_axis.axis.ticker = self.x_ticker
        self.y_axis.width_min = 70
        self.y_axis.width_max = 70
        self.x_axis.height_min = 45
        self.x_axis.height_max = 45
        self.grid.add_widget(self.y_axis, row=0, col=0)
        self.grid.add_widget(self.x_axis, row=1, col=1)
        self.y_axis.link_view(self.view)
        self.x_axis.link_view(self.view)
        self.canvas.events.mouse_wheel.connect(self._scroll_paused_vertical)

        self.background_lines = [
            scene.Line(
                pos=np.zeros((0, 2), dtype=np.float32),
                color=self._background_color(index),
                width=1,
                parent=self.view.scene,
            )
            for index in range(MAX_BACKGROUND_LINES)
        ]

        self.current_line = scene.Line(
            pos=np.zeros((0, 2), dtype=np.float32),
            color=(0.10, 0.75, 1.00, 1.00),
            width=3,
            parent=self.view.scene,
        )
        self.current_markers = scene.Markers(parent=self.view.scene)

        self.title = scene.Text(
            "",
            parent=self.view.scene,
            color="white",
            font_size=12,
            anchor_x="left",
            anchor_y="top",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

        self.timer = vispy_app.Timer(
            interval=POLL_INTERVAL_SEC,
            connect=self._on_timer,
            start=True,
        )
        self._refresh_camera()
        self._redraw()

    def _pregenerate_history(self, duration_sec):
        for t in np.arange(0.0, duration_sec, POLL_INTERVAL_SEC):
            self.samples.append((float(t), self.signal.value(float(t))))

    def set_period_sec(self, value):
        self.period_sec = float(value)
        if self.is_paused:
            rect = self.view.camera.rect
            self.view.camera.rect = (0.0, rect.bottom, self.period_sec, rect.height)
        else:
            self._refresh_camera()
        self._redraw()

    def set_paused(self, paused):
        self.is_paused = paused
        self.view.camera.interactive = False
        if paused:
            self.timer.stop()
            self.paused_now = self.samples[-1][0] if self.samples else None
            self._lock_paused_horizontal()
            self._redraw()
        else:
            self.paused_now = None
            self._refresh_camera()
            self._redraw()
            self.timer.start()

    def _on_timer(self, _event):
        now = perf_counter() - self.started_at
        self.samples.append((now, self.signal.value(now)))
        self._redraw()

    def _redraw(self):
        if len(self.samples) < 2:
            return

        now = self._current_display_time()
        raw = np.asarray(self.samples, dtype=np.float32)

        current_points = self._window_points(raw, now - self.period_sec, now, 0.0)
        self.current_line.set_data(current_points)
        self.current_markers.set_data(
            current_points[-min(len(current_points), 60) :],
            face_color=(1.0, 1.0, 1.0, 1.0),
            edge_color=(0.0, 0.0, 0.0, 1.0),
            size=4,
        )

        for index, line in enumerate(self.background_lines, start=1):
            window_end = now - self.period_sec * index
            window_start = window_end - self.period_sec
            line.set_data(
                self._window_points(
                    raw,
                    window_start,
                    window_end,
                    -PERIOD_LANE_HEIGHT * index,
                )
            )

        self.title.text = (
            f"Период: {self.period_sec:.0f} c. "
            "Текущий период сверху, прошлые периоды ниже как кадры пленки."
        )
        rect = self.view.camera.rect
        self._update_x_axis_time_offset(rect, now)
        self.title.pos = (rect.left + rect.width * 0.015, rect.top - 0.15)

    def _current_display_time(self):
        if self.is_paused and self.paused_now is not None:
            return self.paused_now
        return perf_counter() - self.started_at

    def _window_points(self, raw, start, end, y_offset):
        if end <= 0:
            return np.zeros((0, 2), dtype=np.float32)

        clipped_start = max(0.0, start)
        mask = (raw[:, 0] >= clipped_start) & (raw[:, 0] <= end)
        points = raw[mask]
        if len(points) == 0:
            return np.zeros((0, 2), dtype=np.float32)

        x = points[:, 0] - start
        y = points[:, 1] + y_offset
        return np.column_stack((x, y)).astype(np.float32)

    def _refresh_camera(self):
        self.view.camera.rect = (0.0, -1.0, self.period_sec, 3.4)

    def _scroll_paused_vertical(self, event):
        if not self.is_paused:
            return

        _, delta_y = event.delta
        if delta_y == 0:
            return

        rect = self.view.camera.rect
        step = PERIOD_LANE_HEIGHT * 0.45
        self.view.camera.rect = (
            0.0,
            rect.bottom + delta_y * step,
            self.period_sec,
            rect.height,
        )
        self._redraw()
        event.handled = True

    def _lock_paused_horizontal(self):
        rect = self.view.camera.rect
        self.view.camera.rect = (0.0, rect.bottom, self.period_sec, rect.height)

    def _update_x_axis_time_offset(self, rect, now):
        center_y = rect.bottom + rect.height / 2.0
        lane_index = max(0, int(round(-center_y / PERIOD_LANE_HEIGHT)))
        self.x_ticker.time_offset = now - self.period_sec * (lane_index + 1)
        self.x_axis.axis._need_update = True
        self.x_axis.axis.update()

    def _background_color(self, index):
        return (0.65, 0.70, 0.80, 0.34)


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vispy history overlay demo")
        self.resize(1100, 700)

        self.plot = HistoryPlot()

        self.period_spin = QSpinBox()
        self.period_spin.setRange(5, 300)
        self.period_spin.setSingleStep(5)
        self.period_spin.setSuffix(" c")
        self.period_spin.setValue(int(self.plot.period_sec))
        self.period_spin.valueChanged.connect(self.plot.set_period_sec)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setFocusPolicy(Qt.NoFocus)
        self.pause_btn.toggled.connect(self._pause_toggled)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Временной интервал:"))
        controls.addWidget(self.period_spin)
        controls.addWidget(self.pause_btn)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.plot)

    def _pause_toggled(self, checked):
        self.plot.set_paused(checked)
        self.pause_btn.setText("Продолжить" if checked else "Пауза")


if __name__ == "__main__":
    app = QApplication([])
    window = DemoWindow()
    window.show()
    app.exec()
