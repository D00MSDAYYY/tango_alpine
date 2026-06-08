from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QTabWidget


class ConfiguratorDialog(QDialog):
    def __init__(self, configurators: dict | None = None, parent=None):
        super().__init__(parent)

        self.configurators = configurators or {}

        self._setup_ui()
        self._connect_signals()

    def set_configurator(self, name, conf):
        conf.name = name
        self.configurators[name] = conf
        self.accepted.connect(conf._on_accept)

        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                self.tab_widget.widget(i).deleteLater()  # type: ignore
                self.tab_widget.removeTab(i)
                self.tab_widget.insertTab(i, conf, name)
                return
        self.tab_widget.addTab(conf, name)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        for name, conf in self.configurators.items():
            self.set_configurator(name, conf)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)

    def _connect_signals(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
