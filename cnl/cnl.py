from typing import Literal

from pydantic import Field, BaseModel
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtCore import Signal, QSize
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QDialog,
    QHBoxLayout,
    QPushButton,
)
from vispy.color import Color

from aux.gui.handy_enums import *
from aux.polymorphic_field_handlers import PolymorphicBase
from aux.settings_decorators import with_settings_property, settings_with_signals

from conf.conf_dialog import ConfiguratorDialog
from conf.appearance_conf import AppearenceConfigurator


class _Appearence(BaseModel):
    line_width: float = Field(default=1.0)
    line_color: LineColor = Field(default_factory=random_line_color) # type: ignore

Appearence = settings_with_signals(_Appearence)


class _ChannelSettings(PolymorphicBase):
    type: Literal["ChannelSettings"] = "ChannelSettings"
    name: str = Field(default="безымянный_канал")
    units: str | None = Field(default=None)

    appearence: _Appearence = Field(default_factory=_Appearence)


ChannelSettings = settings_with_signals(_ChannelSettings)


@with_settings_property()
class _Channel(QWidget):
    updated = Signal(object)
    close_requested = Signal(object)
    error_occurred = Signal(str)
    stopped = Signal()

    def __init__(self, settings):
        super().__init__()

        self.settings = settings
        self.new_data = None
        self.data = []

        self._setup_ui()
        self._connect_signals()

    def start(self):
        raise

    def stop(self):
        raise

    def create_plot_curve(self, plot_curve_factory):
        return plot_curve_factory.create_curve(self)

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def _setup_ui(self):
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#3a3a3a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f0f0"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)

        color_wgt = QWidget()
        self.color_wgt = color_wgt
        color_wgt.setFixedSize(20, 20)
        self._update_color_indicator()

        self.name_label = QLabel("")
        self.name_label.setPalette(palette)

        self.name_label.setText(self.settings.name)
        self.settings.name_changed.connect(self.name_label.setText)

        sq_side = 36
        icon_size = QSize(29, 29)
        fixed_w = sq_side
        fixed_h = sq_side

        palette_btn = QPushButton()
        self.palette_btn = palette_btn
        palette_btn.setFlat(True)
        palette_btn.setFixedSize(fixed_w, fixed_h)
        palette_btn.setIcon(QIcon(":/icons/channel_settings.png"))
        palette_btn.setIconSize(icon_size)
        palette_btn.setToolTip("Настройки канала")

        close_btn = QPushButton()
        self.close_btn = close_btn
        close_btn.setFlat(True)
        close_btn.setFixedSize(fixed_w, fixed_h)
        close_btn.setIcon(QIcon(":/icons/close.png"))
        close_btn.setIconSize(icon_size)
        close_btn.setToolTip("Закрыть канал")

        main_layout.addWidget(color_wgt)
        main_layout.addWidget(self.name_label)
        main_layout.addStretch()
        main_layout.addWidget(palette_btn)
        main_layout.addWidget(close_btn)

    def _update_color_indicator(self):
        color_name = self.settings.appearence.line_color.value
        self.color_wgt.setStyleSheet(f"background-color: {Color(color_name).hex};")

    def _connect_signals(self):
        self.close_btn.clicked.connect(lambda flag: self._btn_close_clicked())

        self.palette_btn.clicked.connect(self._btn_palette_clicked)
        self.settings.appearence.line_color_changed.connect(
            self._update_color_indicator
        )

    def _btn_palette_clicked(self):
        conf = AppearenceConfigurator(sett=self.settings.appearence)
        conf_dialog = ConfiguratorDialog(configurators={"Общее": conf})
        if conf_dialog.exec() == QDialog.DialogCode.Accepted:
            pass  #  done

    def _btn_close_clicked(self):
        self.close_requested.emit(self)
