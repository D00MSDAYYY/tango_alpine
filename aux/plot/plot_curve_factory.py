from aux.plot.curve import Pen


class PlotCurveFactory:
    def __init__(self, plot_widget):
        self.plot_widget = plot_widget

    def create_curve(self, cnl):
        pen = Pen(
            color=cnl.settings.appearence.line_color.value,
            width=cnl.settings.appearence.line_width,
            show_dots=cnl.settings.appearence.show_dots,
        )
        return self.plot_widget.add_curve(pen)

    def update_curve_style(self, cnl, curve):
        appearence = cnl.settings.appearence
        curve.set_style(
            color=appearence.line_color.value,
            width=appearence.line_width,
            show_dots=appearence.show_dots,
        )
