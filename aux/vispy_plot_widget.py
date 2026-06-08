import numpy as np
from vispy import scene
from vispy.visuals.axis import Ticker
from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget


PERIOD_LANE_HEIGHT = 3.0
MAX_BACKGROUND_LINES = 24


class FormattedTicker(Ticker):
    def __init__(self, axis, formatter, anchors=None, min_label_spacing=75):
        super().__init__(axis, anchors=anchors)
        self._formatter = formatter
        self._min_label_spacing = min_label_spacing

    def _get_tick_frac_labels(self):
        major_frac, minor_frac, _ = super()._get_tick_frac_labels()
        major_frac = self._thin_major_ticks(major_frac)
        domain_start, domain_end = self.axis.domain
        if len(major_frac) == 0:
            return major_frac, minor_frac, []
        values = domain_start + major_frac * (domain_end - domain_start)
        labels = [self._formatter(value) for value in values]
        return major_frac, minor_frac, labels

    def _thin_major_ticks(self, major_frac):
        if len(major_frac) < 2 or self.axis.pos is None:
            return major_frac

        axis_length = np.linalg.norm(self.axis.pos[1] - self.axis.pos[0])
        if axis_length <= 0:
            return major_frac

        step = 1
        while len(major_frac[::step]) > 1:
            label_spacing = axis_length / (len(major_frac[::step]) - 1)
            if label_spacing >= self._min_label_spacing:
                break
            step += 1

        return major_frac[::step]


class LaneValueTicker(Ticker):
    def __init__(self, axis, lane_height_getter=None):
        super().__init__(axis)
        self._lane_height_getter = lane_height_getter or (lambda: PERIOD_LANE_HEIGHT)

    def _get_tick_frac_labels(self):
        major_frac, minor_frac, _ = super()._get_tick_frac_labels()
        domain_start, domain_end = self.axis.domain
        if len(major_frac) == 0:
            return major_frac, minor_frac, []
        values = domain_start + major_frac * (domain_end - domain_start)
        labels = [self._format_lane_value(value) for value in values]
        return major_frac, minor_frac, labels

    def _format_lane_value(self, value):
        lane_height = max(PERIOD_LANE_HEIGHT, float(self._lane_height_getter()))
        lane_offset = np.floor((value + lane_height / 2.0) / lane_height)
        lane_offset = min(0.0, lane_offset * lane_height)
        return f"{value - lane_offset:.1f}"


class TimeAxisWidget(scene.AxisWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unfreeze()
        self.time_offset = 0.0
        self.freeze()

    def _view_changed(self, event=None):
        tr = self.node_transform(self._linked_view.scene)
        p1, p2 = tr.map(self._axis_ends())
        if self.orientation in ("left", "right"):
            self.axis.domain = (p1[1], p2[1])
        else:
            self.axis.domain = (p1[0] + self.time_offset, p2[0] + self.time_offset)


class VispyPlot(QWidget):
    class Pen:
        def __init__(self, color, width=1.0, show_dots=False):
            self.color = color
            self.width = width
            self.show_dots = show_dots

    class Curve:
        def __init__(
            self,
            vispy_line,
            vispy_markers,
            history_lines,
            parent_plot,
            color,
            show_dots,
        ):
            self._line = vispy_line
            self._markers = vispy_markers
            self._history_lines = history_lines
            self._parent_plot = parent_plot
            self._color = color
            self._show_dots = show_dots
            self._data = None

        def setData(self, data, refresh=True):
            self._data = np.asarray(data, dtype=np.float64)
            if refresh:
                self._parent_plot.refresh()

        def _set_visual_data(self, data, history_data):
            self._line.set_data(data)
            self._markers.set_data(
                data,
                face_color=self._color,
                edge_color=self._color,
                size=5,
            )
            self._markers.visible = self._show_dots and len(data) > 0
            for line, line_data in zip(self._history_lines, history_data):
                line.set_data(line_data)
            for line in self._history_lines[len(history_data):]:
                line.set_data(np.empty((0, 2), dtype=np.float32))

        def setColor(self, color):
            self._color = color
            self._line.set_data(color=color)
            history_color = self._history_color()
            for line in self._history_lines:
                line.set_data(color=history_color)
            self._parent_plot.refresh()

        def setWidth(self, width):
            self._line.set_data(width=width)
            for line in self._history_lines:
                line.set_data(width=max(1.0, float(width) * 0.65))

        def setShowDots(self, show_dots):
            self._show_dots = show_dots
            self._markers.visible = show_dots

        def _history_color(self):
            return self._parent_plot._history_color(self._color)

    def __init__(self):
        super().__init__()
        canvas = scene.SceneCanvas(keys="interactive", show=True)
        grid = canvas.central_widget.add_grid(spacing=0, margin=0)

        viewbox = grid.add_view(row=0, col=1, camera="panzoom")

        x_axis = TimeAxisWidget(orientation="bottom")
        x_axis.axis.ticker = FormattedTicker(x_axis.axis, self._format_x_tick_as_time)
        grid.add_widget(x_axis, row=1, col=1)
        x_axis.link_view(viewbox)

        y_axis = scene.AxisWidget(orientation="left")
        y_axis.axis.ticker = LaneValueTicker(y_axis.axis, self._lane_height)
        grid.add_widget(y_axis, row=0, col=0)
        y_axis.link_view(viewbox)

        y_axis.width_min = 80
        y_axis.width_max = 80
        x_axis.height_min = 60
        x_axis.height_max = 60

        self.canvas = canvas
        self.grid = grid
        self.viewbox = viewbox
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.period_sec = 30.0
        self.history_sec = self.period_sec * MAX_BACKGROUND_LINES
        self.paused_lane_height = PERIOD_LANE_HEIGHT
        self.max_plot_points = 5000
        self.paused = False
        self.paused_time_reference = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

        self.curves = set()
        self.canvas.events.mouse_wheel.connect(self._scroll_paused_vertical)

    def set_x_axis_time_reference(self, value):
        if isinstance(value, datetime):
            value = value.timestamp()
        self.x_axis.time_offset = float(value)
        self.x_axis._view_changed()
        self.x_axis.axis._need_update = True
        self.x_axis.axis.update()

    def set_period(self, value):
        self.period_sec = max(1.0, float(value))
        if self.paused:
            rect = self.viewbox.camera.rect
            self.viewbox.camera.rect = (0.0, rect.bottom, self.period_sec, rect.height)
        else:
            self._refresh_live_camera()
        self.refresh()

    def set_history_range(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = self.period_sec * MAX_BACKGROUND_LINES
        self.history_sec = max(0.0, value)
        self.refresh()

    def set_max_plot_points(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 5000
        self.max_plot_points = max(2, value)
        self.refresh()

    def set_paused(self, paused, time_reference=None):
        self.paused = bool(paused)
        self.viewbox.camera.interactive = False
        if self.paused:
            if isinstance(time_reference, datetime):
                time_reference = time_reference.timestamp()
            self.paused_time_reference = float(time_reference) if time_reference else self._latest_timestamp()
            self._reset_paused_camera()
        else:
            self.paused_time_reference = None
            self._refresh_live_camera()
        self.refresh()

    def set_x_axis_label(self, label):
        self.x_axis.axis.axis_label = label
        self.x_axis.axis.update()

    def set_y_axis_label(self, label):
        self.y_axis.axis.axis_label = label
        self.y_axis.axis.update()

    def set_axis_labels(self, x_label, y_label):
        self.set_x_axis_label(x_label)
        self.set_y_axis_label(y_label)

    def plotCurve(self, dots_coords, pen):
        line = scene.Line(
            pos=dots_coords,
            color=pen.color,
            width=pen.width,
            parent=self.viewbox.scene,
        )  # type: ignore
        history_lines = [
            scene.Line(
                pos=np.empty((0, 2), dtype=np.float32),
                color=self._history_color(pen.color),
                width=max(1.0, float(pen.width) * 0.65),
                parent=self.viewbox.scene,
            )
            for _ in range(MAX_BACKGROUND_LINES)
        ]
        markers = scene.Markers(parent=self.viewbox.scene)
        curve = self.Curve(line, markers, history_lines, self, pen.color, pen.show_dots)
        self.curves.add(curve)
        curve.setData(dots_coords)
        return curve

    def removeCurve(self, curve):
        self.curves.discard(curve)
        curve._line.parent = None
        curve._markers.parent = None
        for line in curve._history_lines:
            line.parent = None

        del curve

    def refresh(self):
        now = self._display_time_reference()
        if now is None:
            return

        if self.paused:
            self.paused_lane_height = self._paused_lane_height(now)

        live_y_values = []
        for curve in self.curves:
            current_data = self._window_points(curve._data, now - self.period_sec, now, 0.0)
            if not self.paused and len(current_data) > 0:
                live_y_values.append(current_data[:, 1])
            history_data = []
            for index in range(1, self._history_window_count() + 1):
                window_end = now - self.period_sec * index
                window_start = window_end - self.period_sec
                y_offset = -self._lane_height() * index if self.paused else 0.0
                line_data = self._window_points(
                    curve._data,
                    window_start,
                    window_end,
                    y_offset,
                )
                if not self.paused and len(line_data) > 0:
                    live_y_values.append(line_data[:, 1])
                history_data.append(line_data)
            curve._set_visual_data(current_data, history_data)

        self._update_x_axis_time_reference(now)
        if self.paused:
            self._lock_paused_horizontal()
        else:
            self._refresh_live_camera(live_y_values)
        self.canvas.update()

    def autoRange(self, margin=0.00000001):
        if self.paused:
            self._lock_paused_horizontal()
        else:
            self._refresh_live_camera()
        return

        has_data, x_min, x_max, y_min, y_max = self._get_data_bounds()
        if not has_data:
            self.viewbox.camera.set_range(x=(0, 1), y=(0, 1))
            return

        # Обработка X
        if np.isfinite(x_min) and np.isfinite(x_max):
            x_range = x_max - x_min
            if x_range == 0:
                x_min -= 1.0
                x_max += 1.0
            x_margin = (x_max - x_min) * margin
            x_left = x_min - x_margin
            x_right = x_max + x_margin
        else:
            # Если нет корректных X, оставляем текущие
            rect = self.viewbox.camera.rect
            x_left, x_right = rect.left, rect.left + rect.width

        # Обработка Y
        if np.isfinite(y_min) and np.isfinite(y_max):
            y_range = y_max - y_min
            if y_range == 0:
                y_min -= 1.0
                y_max += 1.0
            y_margin = (y_max - y_min) * margin
            y_bottom = y_min - y_margin
            y_top = y_max + y_margin
        else:
            rect = self.viewbox.camera.rect
            y_bottom, y_top = rect.bottom, rect.bottom + rect.height

        self.viewbox.camera.set_range(x=(x_left, x_right), y=(y_bottom, y_top))

    def _get_data_bounds(self):
        x_min, x_max = np.inf, -np.inf
        y_min, y_max = np.inf, -np.inf
        has_data = False
        for curve in self.curves:
            pos = curve._line.pos
            if pos is None or len(pos) == 0:
                continue
            has_data = True
            cur_x_min = np.nanmin(pos[:, 0])
            cur_x_max = np.nanmax(pos[:, 0])
            cur_y_min = np.nanmin(pos[:, 1])
            cur_y_max = np.nanmax(pos[:, 1])
            x_min = min(x_min, cur_x_min)
            x_max = max(x_max, cur_x_max)
            y_min = min(y_min, cur_y_min)
            y_max = max(y_max, cur_y_max)
        return has_data, x_min, x_max, y_min, y_max

    def _format_x_tick_as_time(self, value):
        return datetime.fromtimestamp(float(value)).strftime("%H:%M:%S")

    def _window_points(self, data, start, end, y_offset):
        if data is None or len(data) == 0 or end <= 0:
            return np.empty((0, 2), dtype=np.float32)

        clipped_start = max(0.0, start)
        mask = (data[:, 0] >= clipped_start) & (data[:, 0] <= end)
        points = data[mask]
        if len(points) == 0:
            return np.empty((0, 2), dtype=np.float32)
        points = self._thin_points(points)

        x = points[:, 0] - start
        y = points[:, 1] + y_offset
        return np.column_stack((x, y)).astype(np.float32)

    def _thin_points(self, points):
        if len(points) <= self.max_plot_points:
            return points
        indexes = np.linspace(
            0,
            len(points) - 1,
            self.max_plot_points,
            dtype=np.int64,
        )
        return points[indexes]

    def _display_time_reference(self):
        if self.paused and self.paused_time_reference is not None:
            return self.paused_time_reference
        return self._latest_timestamp()

    def _history_window_count(self):
        if self.history_sec <= 0 or self.period_sec <= 0:
            return 0
        return min(
            MAX_BACKGROUND_LINES,
            int(np.ceil(self.history_sec / self.period_sec)),
        )

    def _latest_timestamp(self):
        latest = None
        for curve in self.curves:
            if curve._data is None or len(curve._data) == 0:
                continue
            curve_latest = float(curve._data[-1, 0])
            latest = curve_latest if latest is None else max(latest, curve_latest)
        return latest

    def _update_x_axis_time_reference(self, now):
        rect = self.viewbox.camera.rect
        if self.paused:
            center_y = rect.bottom + rect.height / 2.0
            lane_index = max(0, int(round(-center_y / self._lane_height())))
        else:
            lane_index = 0
        self.set_x_axis_time_reference(now - self.period_sec * (lane_index + 1))

    def _refresh_live_camera(self, y_values=None):
        y_bottom, y_height = self._live_y_rect(y_values)
        self.viewbox.camera.rect = (0.0, y_bottom, self.period_sec, y_height)

    def _live_y_rect(self, y_values):
        if not y_values:
            return -1.0, 2.0

        y = np.concatenate(y_values)
        y = y[np.isfinite(y)]
        if len(y) == 0:
            return -1.0, 2.0

        y_min = float(np.min(y))
        y_max = float(np.max(y))
        if y_min == y_max:
            margin = max(abs(y_min) * 0.1, 1.0)
        else:
            margin = (y_max - y_min) * 0.12

        y_bottom = y_min - margin
        y_top = y_max + margin
        return y_bottom, max(y_top - y_bottom, 1e-6)

    def _scroll_paused_vertical(self, event):
        if not self.paused:
            return
        _, delta_y = event.delta
        if delta_y == 0:
            return

        rect = self.viewbox.camera.rect
        step = self._lane_height()
        self.viewbox.camera.rect = (
            0.0,
            rect.bottom + delta_y * step,
            self.period_sec,
            rect.height,
        )
        self.refresh()
        event.handled = True

    def _lock_paused_horizontal(self):
        rect = self.viewbox.camera.rect
        self.viewbox.camera.rect = (0.0, rect.bottom, self.period_sec, rect.height)

    def _reset_paused_camera(self):
        y_bottom, y_height = self._paused_top_lane_rect()
        self.viewbox.camera.rect = (0.0, y_bottom, self.period_sec, y_height)

    def _paused_top_lane_rect(self):
        now = self._display_time_reference()
        if now is None:
            return -1.0, 2.0
        y_values = []
        for curve in self.curves:
            data = self._window_points(curve._data, now - self.period_sec, now, 0.0)
            if len(data) > 0:
                y_values.append(data[:, 1])
        return self._live_y_rect(y_values)

    def _lane_height(self):
        return max(PERIOD_LANE_HEIGHT, float(self.paused_lane_height))

    def _paused_lane_height(self, now):
        y_values = []
        for curve in self.curves:
            current_data = self._window_points(curve._data, now - self.period_sec, now, 0.0)
            if len(current_data) > 0:
                y_values.append(current_data[:, 1])
            for index in range(1, self._history_window_count() + 1):
                window_end = now - self.period_sec * index
                window_start = window_end - self.period_sec
                line_data = self._window_points(curve._data, window_start, window_end, 0.0)
                if len(line_data) > 0:
                    y_values.append(line_data[:, 1])

        _, y_height = self._live_y_rect(y_values)
        return max(PERIOD_LANE_HEIGHT, y_height * 1.15)

    def _history_color(self, color):
        try:
            from vispy.color import Color

            rgba = Color(color).rgba
            return (rgba[0], rgba[1], rgba[2], 0.24)
        except Exception:
            return (0.65, 0.70, 0.80, 0.24)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.canvas.size = event.size().width(), event.size().height()
        self.canvas.update()
