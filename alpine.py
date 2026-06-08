import gc
import traceback
from typing import List
from datetime import timedelta

import numpy as np
from pydantic import BaseModel, Field
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtWidgets import QToolBar, QMainWindow, QDialog, QSplitter, QPushButton

from conf.conf_dialog import ConfiguratorDialog
from conf.alpine_conf import AlpineConfigurator
from cnl.cnl import _ChannelSettings
from cnl.cnl_maker import ChannelMaker
from aux.vispy_plot_widget import VispyPlot
from aux.plot_curve_factory import PlotCurveFactory
from aux.config_store import ConfigStoreFactory
from aux.gui.widgets.legend import LegendWidget
from aux.gui.widgets.opener_dialog import OpenerDialog
from aux.gui.widgets.searchable_list import SearchableListView
from aux.polymorphic_field_handlers import polymorphic_list_field_handlers
from aux.settings_decorators import (
    with_settings_property,
    settings_with_signals,
    get_saving_trigger,
)


class _AlpineSettings(BaseModel):
    time_range: timedelta = Field(default=timedelta(seconds=30))
    history_range: timedelta = Field(default=timedelta(seconds=750))
    max_redraw_hz: float = Field(default=20.0)
    max_plot_points: int = Field(default=5000)
    x_axis_label: str = Field(default="X")
    y_axis_label: str = Field(default="Y")

    cnls_setts: List[_ChannelSettings] = Field(default_factory=list)
    _val_cnls_setts, _ser_cnls_setts = polymorphic_list_field_handlers(
        _ChannelSettings, "cnls_setts"
    )


AlpineSettings = settings_with_signals(_AlpineSettings)


@with_settings_property()
class Alpine(QMainWindow):
    cnl_created_with_sett = Signal(object)
    cnl_closed_with_sett = Signal(object)
    cnl_deleted_with_sett = Signal(object)

    settings_created = Signal(object)

    def __init__(self, sett_path, config_store_factory=None):
        super().__init__()
        self.config_store_factory = config_store_factory or ConfigStoreFactory()
        self._setup_settings(sett_path)
        self.time_range = self.settings.time_range
        self.history_range = self.settings.history_range
        self.stop_flag = False
        self.cnl_to_curve = {}
        self._dirty_cnls = set()
        self._is_shutting_down = False

        # TODO this violates DI principles but ok for now
        self.cnl_maker = ChannelMaker(self)

        self._setup_ui()
        self._setup_plot_update_timer()
        self._setup_stats_timer()
        self._setup_gc_timer()

    ###################
    #                 #
    #    interface    #
    #                 #
    ###################
    def add_cnl(self, cnl):
        self.legend.add_cnl(cnl)

        curve = cnl.create_plot_curve(self.plot_curve_factory)
        if curve is not None:
            self.cnl_to_curve[cnl] = curve

        cnl.close_requested.connect(self.remove_cnl)
        cnl.updated.connect(self._on_cnl_updated)
        cnl.error_occurred.connect(
            lambda error_text, cnl=cnl: self._on_cnl_error(cnl, error_text),
            Qt.ConnectionType.QueuedConnection,
        )

        cnl.settings.appearence.line_color_changed.connect(
            lambda color, cnl=cnl: self._update_curve_style(cnl),
            self.Qt_DirConn,
        )
        cnl.settings.appearence.line_width_changed.connect(
            lambda width, cnl=cnl: self._update_curve_style(cnl),
            self.Qt_DirConn,
        )
        cnl.settings.appearence.show_dots_changed.connect(
            lambda show_dots, cnl=cnl: self._update_curve_style(cnl),
            self.Qt_DirConn,
        )
        try:
            cnl.start()
        except Exception as e:
            error_text = traceback.format_exc()
            print(str(e))
            self.remove_cnl(cnl)
            self.add_error_cnl(cnl.settings, error_text)

    def add_error_cnl(self, sett, error_text):
        self.add_cnl(self.cnl_maker.create_error_cnl(sett, error_text))

    def remove_cnl(self, cnl):
        self._dirty_cnls.discard(cnl)
        if curve := self.cnl_to_curve.pop(cnl, None):
            self.plot_widget.removeCurve(curve)
        try:
            cnl.stop()
        except Exception as e:
            print(str(e))
        self.legend.remove_cnl(cnl)

    def _on_cnl_error(self, cnl, error_text):
        if self._is_shutting_down or cnl not in self.cnl_to_curve:
            return
        sett = cnl.settings
        self.remove_cnl(cnl)
        self.add_error_cnl(sett, error_text)

    def shutdown(self):
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        if self._stats_timer:
            self._stats_timer.stop()
        if self._gc_timer:
            self._gc_timer.stop()
        if self._plot_update_timer:
            self._plot_update_timer.stop()

        for cnl in list(self.cnl_to_curve):
            self.remove_cnl(cnl)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    ###########################
    #                         #
    #    actions callbacks    #
    #                         #
    ###########################
    def _action_add_triggered(self):
        crts_list_view = SearchableListView(
            items=self.settings.cnls_setts,
            item_maker=lambda cnl_sett: f"{cnl_sett.name}",
            multi_select=True,
        )
        dialog = OpenerDialog(crts_list_view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for sett in crts_list_view.get_selected_data():
                all_channels = self.legend.get_channels()
                if sett.name in [cnl.settings.name for cnl in all_channels]:
                    continue
                try:
                    cnl = self.cnl_maker.create_cnl(sett)
                    self.add_cnl(cnl)
                except Exception:
                    self.add_error_cnl(sett, traceback.format_exc())

    def _action_palette_triggered(self):
        conf = AlpineConfigurator(sett=self.settings)
        conf_dialog = ConfiguratorDialog(configurators={"Общее": conf})
        if conf_dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    def _action_pause_triggered(self):
        self.stop_flag = not self.stop_flag
        self.plot_widget.set_paused(self.stop_flag)
        if not self.stop_flag:
            self._redraw_all_curves()
        self.pause_action.setIcon(
            QIcon(":/icons/resume.png" if self.stop_flag else ":/icons/pause.png")
        )
        self.pause_action.setToolTip(
            "Продолжить обновление графика"
            if self.stop_flag
            else "Пауза обновления графика"
        )

    ########################
    #                      #
    #    setup funtions    #
    #                      #
    ########################
    def _setup_settings(self, sett_path):
        self.settings_path = sett_path
        self.config_store = self.config_store_factory.create(self.settings_path)
        try:
            obj = self.config_store.load(self.settings_path)
            self.settings: _AlpineSettings = AlpineSettings(**obj)  # type: ignore

            get_saving_trigger().triggered.connect(
                self._save_all_settings, self.Qt_DirConn
            )
            self.settings.time_range_changed.connect(
                self._on_time_range_changed,
                self.Qt_DirConn,
            )  # type: ignore
            self.settings.history_range_changed.connect(
                self._on_history_range_changed,
                self.Qt_DirConn,
            )  # type: ignore
            self.settings.max_redraw_hz_changed.connect(
                self._on_max_redraw_hz_changed,
                self.Qt_DirConn,
            )  # type: ignore
            self.settings.max_plot_points_changed.connect(
                self._on_max_plot_points_changed,
                self.Qt_DirConn,
            )  # type: ignore
            self.settings.x_axis_label_changed.connect(
                self._on_x_axis_label_changed,
                self.Qt_DirConn,
            )  # type: ignore
            self.settings.y_axis_label_changed.connect(
                self._on_y_axis_label_changed,
                self.Qt_DirConn,
            )  # type: ignore

            self.settings_created.emit(self.settings)
        except Exception as e:
            print("exception in settings")
            raise

    def _setup_ui(self):
        self._setup_toolbar()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        plot_widget = VispyPlot()
        self.plot_widget = plot_widget
        self.plot_widget.set_period(self.settings.time_range.total_seconds())
        self.plot_widget.set_history_range(self.settings.history_range.total_seconds())
        self.plot_widget.set_max_plot_points(self.settings.max_plot_points)
        self.plot_curve_factory = PlotCurveFactory(plot_widget)
        plot_widget.set_axis_labels(
            self.settings.x_axis_label,
            self.settings.y_axis_label,
        )

        self.legend = LegendWidget()

        splitter.addWidget(self.plot_widget)
        splitter.addWidget(self.legend)
        splitter.setSizes([int(self.width() * 0.75), int(self.width() * 0.25)])

        self.setCentralWidget(splitter)

    def _setup_toolbar(self):
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(38, 38))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        button_size = QSize(46, 46)
        icon_size = QSize(38, 38)

        self.add_action = QPushButton()
        self.add_action.setFlat(True)
        self.add_action.setFixedSize(button_size)
        self.add_action.setIcon(QIcon(":/icons/add.png"))
        self.add_action.setIconSize(icon_size)
        self.add_action.setToolTip("Добавить канал")
        self.add_action.clicked.connect(self._action_add_triggered, self.Qt_DirConn)
        toolbar.addWidget(self.add_action)

        self.palette_action = QPushButton()
        self.palette_action.setFlat(True)
        self.palette_action.setFixedSize(button_size)
        self.palette_action.setIcon(QIcon(":/icons/axes.png"))
        self.palette_action.setIconSize(icon_size)
        self.palette_action.setToolTip("Настройки внешнего вида")
        self.palette_action.clicked.connect(
            self._action_palette_triggered, self.Qt_DirConn
        )
        toolbar.addWidget(self.palette_action)

        self.pause_action = QPushButton()
        self.pause_action.setFlat(True)
        self.pause_action.setFixedSize(button_size)
        self.pause_action.setIcon(QIcon(":/icons/pause.png"))
        self.pause_action.setIconSize(icon_size)
        self.pause_action.setToolTip("Пауза обновления графика")
        self.pause_action.clicked.connect(
            self._action_pause_triggered, self.Qt_DirConn
        )
        toolbar.addWidget(self.pause_action)

    def _setup_stats_timer(self):
        self._redraw_plot_count = 0
        self._incoming_update_count = 0
        self._redraw_plot_hz = 0.0
        self._incoming_update_hz = 0.0
        self._stats_timer = QTimer()
        self._stats_timer.setInterval(5000)
        self._stats_timer.timeout.connect(self._on_stats_timer)
        self._stats_timer.start()

    def _setup_plot_update_timer(self):
        self._plot_update_timer = QTimer()
        self._plot_update_timer.setInterval(self._redraw_timer_interval_msec())
        self._plot_update_timer.timeout.connect(self._on_plot_update_timer)
        self._plot_update_timer.start()

    def _setup_gc_timer(self):
        self._gc_timer = QTimer()
        self._gc_timer.setInterval(30000)  # 30 секунд
        self._gc_timer.timeout.connect(self._on_gc_timer)
        self._gc_timer.start()

    ############################
    #                          #
    #    settings callbacks    #
    #                          #
    ############################
    def _update_curve_style(self, cnl):
        if curve := self.cnl_to_curve.get(cnl):
            self.plot_curve_factory.update_curve_style(cnl, curve)

    def _on_time_range_changed(self, value):
        self.time_range = value
        self.plot_widget.set_period(value.total_seconds())

    def _on_history_range_changed(self, value):
        self.history_range = value
        self.plot_widget.set_history_range(value.total_seconds())

    def _on_max_redraw_hz_changed(self, value):
        self._plot_update_timer.setInterval(self._redraw_timer_interval_msec(value))

    def _on_max_plot_points_changed(self, value):
        self.plot_widget.set_max_plot_points(value)

    def _on_x_axis_label_changed(self, value):
        self.plot_widget.set_x_axis_label(value)

    def _on_y_axis_label_changed(self, value):
        self.plot_widget.set_y_axis_label(value)

    def _save_all_settings(self):
        self.config_store.save(
            self.settings_path,
            self.settings.model_dump(mode="json"),
        )

    ##########################
    #                        #
    #    timers callbacks    #
    #                        #
    ##########################

    def _on_stats_timer(self):
        if self._redraw_plot_count > 0:
            self._redraw_plot_hz = self._redraw_plot_count / 5.0
        else:
            self._redraw_plot_hz = 0.0
        if self._incoming_update_count > 0:
            self._incoming_update_hz = self._incoming_update_count / 5.0
        else:
            self._incoming_update_hz = 0.0

        self._redraw_plot_count = 0
        self._incoming_update_count = 0
        print(
            f"Частота данных: {self._incoming_update_hz:.1f} Hz, "
            f"перерисовки графика: {self._redraw_plot_hz:.1f} Hz"
        )

    def _on_gc_timer(self):
        collected = gc.collect()
        print(f"🧹 Сборщик мусора вызван (каждые 30 с), удалено объектов: {collected}")

    def _on_plot_update_timer(self):
        if self.stop_flag or not self._dirty_cnls:
            return
        dirty_cnls = list(self._dirty_cnls)
        self._dirty_cnls.clear()
        for cnl in dirty_cnls:
            self._redraw_plot(cnl, refresh=False)
        self.plot_widget.refresh()
        self._redraw_plot_count += 1

    ###############################################
    #                                             #
    #    misc (but most intensitive) callbacks    #
    #                                             #
    ###############################################
    def _on_cnl_updated(self, cnl):
        if self._is_shutting_down or cnl not in self.cnl_to_curve:
            return
        self._incoming_update_count += 1
        self._dirty_cnls.add(cnl)

    def _redraw_plot(self, cnl, refresh=True):
        if self.stop_flag:
            return
        if curve := self.cnl_to_curve.get(cnl):
            pos = self._channel_history_to_points(cnl)
            curve.setData(pos, refresh=refresh)
            if refresh:
                self._redraw_plot_count += 1

    def _redraw_all_curves(self):
        for cnl in list(self.cnl_to_curve):
            self._redraw_plot(cnl, refresh=False)
        self.plot_widget.refresh()
        self._redraw_plot_count += 1

    def _channel_history_to_points(self, cnl):
        self._prune_channel_data(cnl)
        points = []
        for record in cnl.data:
            try:
                timestamp = float(record["timestamp"])
                value = float(record["value"])
            except (KeyError, TypeError, ValueError):
                continue
            points.append((timestamp, value))
        if not points:
            return np.empty((0, 2), dtype=np.float64)
        return np.asarray(points, dtype=np.float64)

    def _prune_channel_data(self, cnl):
        if not cnl.data:
            return
        try:
            latest_ts = float(cnl.data[-1]["timestamp"])
        except (KeyError, TypeError, ValueError):
            return

        keep_seconds = (
            self.time_range.total_seconds()
            + self.history_range.total_seconds()
        )
        cutoff_ts = latest_ts - keep_seconds
        first_keep_idx = 0
        for idx, record in enumerate(cnl.data):
            try:
                if float(record["timestamp"]) >= cutoff_ts:
                    first_keep_idx = idx
                    break
            except (KeyError, TypeError, ValueError):
                continue
        if first_keep_idx > 0:
            del cnl.data[:first_keep_idx]

    def _redraw_timer_interval_msec(self, max_redraw_hz=None):
        if max_redraw_hz is None:
            max_redraw_hz = self.settings.max_redraw_hz
        try:
            max_redraw_hz = float(max_redraw_hz)
        except (TypeError, ValueError):
            max_redraw_hz = 20.0
        max_redraw_hz = max(1.0, max_redraw_hz)
        return max(1, round(1000.0 / max_redraw_hz))

    Qt_DirConn = Qt.ConnectionType.DirectConnection
