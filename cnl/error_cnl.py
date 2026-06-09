from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
    QStyle,
)

from cnl._base import ElidedLabel, _Channel


class ErrorChannel(_Channel):
    def __init__(self, settings, error_text: str, appearance_dialog_factory=None):
        self.error_text = error_text
        super().__init__(settings, appearance_dialog_factory)

    def start(self):
        pass

    def stop(self):
        pass

    def create_plot_curve(self, plot_widget):
        return None

    def _setup_ui(self):
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#8f1d1d"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(6)

        marker = QLabel("!")
        self.marker = marker
        marker.setFixedSize(20, 20)
        marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marker.setPalette(palette)

        self.name_label = ElidedLabel(f"Ошибка: {self.settings.name}")
        self.name_label.setPalette(palette)
        self.name_label.setWordWrap(False)

        sq_side = 36
        icon_size = QSize(29, 29)
        fixed_w = sq_side
        fixed_h = sq_side

        info_btn = QPushButton()
        self.info_btn = info_btn
        info_btn.setFlat(True)
        info_btn.setFixedSize(fixed_w, fixed_h)
        info_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        )
        info_btn.setIconSize(icon_size)
        info_btn.setToolTip("Показать текст ошибки")

        close_btn = QPushButton()
        self.close_btn = close_btn
        close_btn.setFlat(True)
        close_btn.setFixedSize(fixed_w, fixed_h)
        close_btn.setIcon(QIcon(":/icons/close.png"))
        close_btn.setIconSize(icon_size)
        close_btn.setToolTip("Закрыть канал")

        main_layout.addWidget(marker)
        main_layout.addWidget(self.name_label, 1)
        main_layout.addWidget(info_btn)
        main_layout.addWidget(close_btn)
        self.info_btn.clicked.connect(lambda flag: self._show_error())
        self.close_btn.clicked.connect(lambda flag: self.close_requested.emit(self))

    def _show_error(self):
        QMessageBox.critical(
            self,
            f"Ошибка канала {self.settings.name}",
            self.error_text,
        )
