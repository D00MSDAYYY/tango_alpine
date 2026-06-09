from PySide6.QtWidgets import QApplication, QDialog

from aux.gui import resources_rc  # noqa: F401
from alpine import Alpine
from conf.appearance_dialog_factory import AppearanceDialogFactory
from conf.dialog_factory import SettingsDialogFactory
from cnl.factory import ChannelFactory
from aux._config_store import ConfigStoreFactory
from aux.anomaly import AnomalyDetectorFactory
from aux.gui.widgets.channel_picker import ChannelPicker
from aux.plot.vispy_plot_widget import VispyPlot
from aux.plot.plot_curve_factory import PlotCurveFactory
from aux.gui.widgets.legend import LegendWidget
from aux.gui.widgets.settings_picker import SettingsPicker


def main():
    app = QApplication()
    font = app.font()
    if font.pointSize() > 0:
        font.setPointSize(round(font.pointSize() * 1.2))
    elif font.pixelSize() > 0:
        font.setPixelSize(round(font.pixelSize() * 1.2))
    app.setFont(font)

    settings_picker = SettingsPicker()

    if settings_picker.exec() == QDialog.DialogCode.Accepted:
        plot_widget = VispyPlot()
        appearance_dialog_factory = AppearanceDialogFactory()
        alpine = Alpine(
            sett_path=settings_picker.get_file_path(),
            config_store_factory=ConfigStoreFactory(),
            channel_factory=ChannelFactory(appearance_dialog_factory),
            anomaly_detector_factory=AnomalyDetectorFactory(),
            settings_dialog_factory=SettingsDialogFactory(),
            channel_picker=ChannelPicker(),
            plot_widget=plot_widget,
            plot_curve_factory=PlotCurveFactory(plot_widget),
            legend=LegendWidget(),
        )
        app.aboutToQuit.connect(alpine.shutdown)
        alpine.show()
    del settings_picker

    app.exec()


if __name__ == "__main__":
    main()
