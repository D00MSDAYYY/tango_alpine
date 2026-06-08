import numpy as np


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

    def set_data(self, data, refresh=True):
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

    def set_color(self, color):
        self._color = color
        self._line.set_data(color=color)
        history_color = self._history_color()
        for line in self._history_lines:
            line.set_data(color=history_color)
        self._parent_plot.refresh()

    def set_width(self, width):
        self._line.set_data(width=width)
        for line in self._history_lines:
            line.set_data(width=max(1.0, float(width) * 0.65))

    def set_show_dots(self, show_dots):
        self._show_dots = show_dots
        self._markers.visible = show_dots

    def set_style(self, color=None, width=None, show_dots=None):
        if color is not None:
            self.set_color(color)
        if width is not None:
            self.set_width(width)
        if show_dots is not None:
            self.set_show_dots(show_dots)

    def _history_color(self):
        return self._parent_plot._history_color(self._color)
