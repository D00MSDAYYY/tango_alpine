from conf.appearance_conf import AppearenceConfigurator
from conf.dialog import ConfiguratorDialog


class AppearanceDialogFactory:
    def create_appearance_dialog(self, appearance_settings):
        return ConfiguratorDialog(
            configurators={
                "Общее": AppearenceConfigurator(sett=appearance_settings),
            }
        )
