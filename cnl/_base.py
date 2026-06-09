from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from vispy.color import Color

from aux.settings.decorators import with_settings_property
from conf._appearance_dialog_factory import _AppearanceDialogFactory


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

    def __init__(
        self,
        settings,
        appearance_dialog_factory: _AppearanceDialogFactory | None = None,
    ):
        super().__init__()

        self.settings = settings
        self.appearance_dialog_factory = appearance_dialog_factory
        self.new_data = None
        self.data = []
        self.anomaly_results = ()
        self.hidden_anomaly_keys = set()
        self.favorite_anomaly_keys = set()
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

        left_btn = QPushButton()
        self.left_btn = left_btn
        left_btn.setFlat(True)
        left_btn.setFixedSize(fixed_w, fixed_h)
        left_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))
        left_btn.setIconSize(icon_size)
        left_btn.setEnabled(False)
        left_btn.setToolTip("Аномалий нет")
        left_btn.clicked.connect(self._show_anomalies)

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
        main_layout.addWidget(left_btn)
        main_layout.addWidget(self.name_label, 1)
        main_layout.addWidget(palette_btn)
        main_layout.addWidget(close_btn)

    def _update_color_indicator(self):
        color_name = self.settings.appearence.line_color.value
        self.color_wgt.setStyleSheet(f"background-color: {Color(color_name).hex};")

    def _btn_palette_clicked(self):
        if self.appearance_dialog_factory is None:
            return
        conf_dialog = self.appearance_dialog_factory.create_appearance_dialog(
            self.settings.appearence,
        )
        if conf_dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    def _btn_close_clicked(self):
        self.close_requested.emit(self)

    def set_anomaly_results(self, strategy_results):
        self.anomaly_results = tuple(strategy_results)
        anomaly_count = self._anomaly_count()
        self.left_btn.setEnabled(anomaly_count > 0)
        if anomaly_count > 0:
            self.left_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            )
            self.left_btn.setToolTip(f"Найдено аномалий: {anomaly_count}")
        else:
            self.left_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)
            )
            self.left_btn.setToolTip("Аномалий нет")

    def _show_anomalies(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Аномалии канала {self.settings.name}")
        dialog.resize(560, 420)

        layout = QVBoxLayout(dialog)
        title = QLabel(f"Найдено аномалий: {self._anomaly_count()}")
        layout.addWidget(title)

        anomaly_list = QListWidget()
        anomaly_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._fill_anomaly_list(anomaly_list)
        layout.addWidget(anomaly_list)

        actions_layout = QHBoxLayout()
        favorite_btn = QPushButton("*")
        favorite_btn.setToolTip("Добавить выбранные записи в избранное")
        clear_btn = QPushButton("Очистить выбранные")
        actions_layout.addWidget(favorite_btn)
        actions_layout.addWidget(clear_btn)
        actions_layout.addStretch(1)
        layout.addLayout(actions_layout)

        def refresh_list():
            self._fill_anomaly_list(anomaly_list)
            title.setText(f"Найдено аномалий: {self._anomaly_count()}")
            self.set_anomaly_results(self.anomaly_results)

        def selected_keys():
            return [
                item.data(Qt.ItemDataRole.UserRole)
                for item in anomaly_list.selectedItems()
                if item.data(Qt.ItemDataRole.UserRole) is not None
            ]

        def clear_selected():
            self.hidden_anomaly_keys.update(selected_keys())
            refresh_list()

        def toggle_selected_favorites():
            for key in selected_keys():
                if key in self.favorite_anomaly_keys:
                    self.favorite_anomaly_keys.remove(key)
                else:
                    self.favorite_anomaly_keys.add(key)
            refresh_list()

        clear_btn.clicked.connect(clear_selected)
        favorite_btn.clicked.connect(toggle_selected_favorites)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec()

    def _anomaly_count(self):
        return sum(
            1
            for result in self.anomaly_results
            for anomaly in result.anomalies
            if self._anomaly_key(result, anomaly) not in self.hidden_anomaly_keys
        )

    def _fill_anomaly_list(self, anomaly_list):
        anomaly_list.clear()
        has_visible_anomalies = False
        for result in self.anomaly_results:
            if not result.anomalies:
                continue
            for anomaly in result.anomalies:
                key = self._anomaly_key(result, anomaly)
                if key in self.hidden_anomaly_keys:
                    continue
                has_visible_anomalies = True
                time_text = datetime.fromtimestamp(anomaly.timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                )[:-3]
                favorite_mark = "* " if key in self.favorite_anomaly_keys else ""
                item = QListWidgetItem(
                    f"{favorite_mark}{time_text} | "
                    f"{result.strategy_name} | {anomaly.name}"
                )
                item.setData(Qt.ItemDataRole.UserRole, key)
                anomaly_list.addItem(item)

        if not has_visible_anomalies:
            item = QListWidgetItem("Аномалий нет")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            anomaly_list.addItem(item)

    def _anomaly_key(self, result, anomaly):
        return (
            result.strategy_name,
            anomaly.name,
            float(anomaly.timestamp),
        )
