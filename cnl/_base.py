from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from vispy.color import Color

from aux.settings.decorators import with_settings_property
from conf.appearance_conf import AppearenceConfigurator
from conf.dialog import ConfiguratorDialog


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setToolTip(text)

    def setText(self, text):
        self._full_text = text
        self.setToolTip(text)
        super().setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            self.width(),
        )
        painter.drawText(
            self.rect(),
            self.alignment() | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


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
        self._last_poll_timestamp = None

        self.settings.appearence.line_color_changed.connect(
            self._update_color_indicator
        )

        self._setup_ui()

    def start(self):
        raise

    def stop(self):
        raise

    def create_plot_curve(self, plot_curve_factory):
        return plot_curve_factory.create_curve(self)

    def register_poll_timing(self, record):
        timestamp = record.get("timestamp") if isinstance(record, dict) else None
        if timestamp is None:
            timestamp = datetime.now().timestamp()

        current_time = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]
        # if self._last_poll_timestamp is None:
        #     print(
        #         f"{self.settings.name}: last_poll=-, "
        #         f"new_poll={current_time}, delta=-"
        #     )
        # else:
        #     last_time = datetime.fromtimestamp(self._last_poll_timestamp).strftime(
        #         "%H:%M:%S.%f"
        #     )[:-3]
        #     delta_msec = (timestamp - self._last_poll_timestamp) * 1000
        #     print(
        #         f"{self.settings.name}: last_poll={last_time}, "
        #         f"new_poll={current_time}, delta={delta_msec:.1f} ms"
        #     )

        self._last_poll_timestamp = timestamp

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def _setup_ui(self):
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#3a3a3a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f0f0"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(6)

        color_wgt = QWidget()
        self.color_wgt = color_wgt
        color_wgt.setFixedSize(20, 20)
        self._update_color_indicator()

        self.name_label = ElidedLabel("")
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
        self.palette_btn.clicked.connect(self._btn_palette_clicked)

        close_btn = QPushButton()
        self.close_btn = close_btn
        close_btn.setFlat(True)
        close_btn.setFixedSize(fixed_w, fixed_h)
        close_btn.setIcon(QIcon(":/icons/close.png"))
        close_btn.setIconSize(icon_size)
        close_btn.setToolTip("Закрыть канал")
        self.close_btn.clicked.connect(lambda flag: self._btn_close_clicked())

        main_layout.addWidget(color_wgt)
        main_layout.addWidget(self.name_label, 1)
        main_layout.addWidget(palette_btn)
        main_layout.addWidget(close_btn)

    def _update_color_indicator(self):
        color_name = self.settings.appearence.line_color.value
        self.color_wgt.setStyleSheet(f"background-color: {Color(color_name).hex};")

    def _btn_palette_clicked(self):
        conf = AppearenceConfigurator(sett=self.settings.appearence)
        conf_dialog = ConfiguratorDialog(configurators={"Общее": conf})
        if conf_dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    def _btn_close_clicked(self):
        self.close_requested.emit(self)
