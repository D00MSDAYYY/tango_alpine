from conf.alpine_conf import AlpineConfigurator
from conf.anomaly_detector_conf import AnomalyDetectorConfigurator
from conf.dialog import ConfiguratorDialog


class SettingsDialogFactory:
    def create_settings_dialog(self, settings):
        return ConfiguratorDialog(
            configurators={
                "Общее": AlpineConfigurator(sett=settings),
                "Детектор": AnomalyDetectorConfigurator(sett=settings),
            }
        )
