import numpy as np

from aux.vispy_plot_widget import VispyPlot


class PlotCurveFactory:
    def __init__(self, plot_widget):
        self.plot_widget = plot_widget

    def create_curve(self, cnl):
        pen = VispyPlot.Pen(
            color=cnl.settings.appearence.line_color.value,
            width=cnl.settings.appearence.line_width,
            show_dots=cnl.settings.appearence.show_dots,
        )
        return self.plot_widget.plotCurve(
            dots_coords=np.empty((0, 2), dtype=np.float32),
            pen=pen,
        )

    def update_curve_style(self, cnl, curve):
        appearence = cnl.settings.appearence
        curve.setColor(color=appearence.line_color.value)
        curve.setWidth(width=appearence.line_width)
        curve.setShowDots(show_dots=appearence.show_dots)
