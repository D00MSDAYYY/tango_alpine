import gc
import json
from typing import List
from datetime import datetime, timedelta

import numpy as np
from pydantic import BaseModel, Field
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal, QThreadPool, QRunnable,  QTimer, QSize
from PySide6.QtWidgets import QToolBar, QMainWindow, QDialog, QSplitter, QPushButton

from conf.conf_dialog import ConfiguratorDialog
from conf.alpine_conf import AlpineConfigurator
from cnl.cnl import _ChannelSettings
from cnl.cnl_maker import ChannelMaker
from aux.vispy_plot_widget import VispyPlot
from aux.gui.widgets.legend import LegendWidget
from aux.gui.widgets.opener_dialog import OpenerDialog
from aux.gui.widgets.searchable_list import SearchableListView
from aux.polymorphic_field_handlers import polymorphic_list_field_handlers
from aux.data_filter_with_binary_search import data_filter_with_binary_search
from aux.settings_decorators import (
    with_settings_property,
    settings_with_signals,
    get_saving_trigger,
)


class _AlpineSettings(BaseModel):
    time_range: timedelta = Field(default=timedelta(seconds=30))
    x_axis_label: str = Field(default="X")
    y_axis_label: str = Field(default="Y")

    cnls_setts: List[_ChannelSettings] = Field(default_factory=list)
    _val_cnls_setts, _ser_cnls_setts = polymorphic_list_field_handlers(
        _ChannelSettings, "cnls_setts"
    )


AlpineSettings = settings_with_signals(_AlpineSettings)


class _FilterDataTask(QRunnable):
    def __init__(self, alpine, cnl, from_dt, to_dt, callback):
        super().__init__()
        self.alpine = alpine
        self.cnl = cnl
        self.from_dt = from_dt
        self.to_dt = to_dt
        self.callback = callback

    def run(self):
        filtered_data = data_filter_with_binary_search(
            self.cnl.data, self.from_dt, self.to_dt
        )

        del self.cnl.data
        self.cnl.data = filtered_data

        if filtered_data:
            to_ts = self.to_dt.timestamp()

            pos = np.array(
                [[d["timestamp"] - to_ts, d["value"]] for d in filtered_data],
                dtype=np.float32,
            )
        else:
            pos = np.empty((0, 2), dtype=np.float32)

        self.callback(self.cnl, pos, self.to_dt)


@with_settings_property()
class Alpine(QMainWindow):
    cnl_created_with_sett = Signal(object)
    cnl_closed_with_sett = Signal(object)
    cnl_deleted_with_sett = Signal(object)

    settings_created = Signal(object)

    def __init__(self, sett_path):
        super().__init__()
        self._setup_settings(sett_path)
        self._setup_ui()
        self._setup_stats_timer()
        self._setup_gc_timer()

        self.time_range = self.settings.time_range
        self.stop_flag = False

        # TODO this violates DI principles but ok for now
        self.cnl_maker = ChannelMaker(self)
        self.cnl_to_curve = {}

        self._threadpool = QThreadPool.globalInstance()
        self._is_shutting_down = False

    ###################
    #                 #
    #    interface    #
    #                 #
    ###################
    def add_cnl(self, cnl):
        self.legend.add_cnl(cnl)

        pen = VispyPlot.Pen(
            color=cnl.settings.appearence.line_color.value,
            width=cnl.settings.appearence.line_width,
        )
        curve = self.plot_widget.plotCurve(
            dots_coords=np.array([[0, 0], [0, 0]], dtype=np.float32),
            pen=pen,
        )
        self.cnl_to_curve[cnl] = curve

        cnl.close_requested.connect(self.remove_cnl)
        cnl.updated.connect(self._on_cnl_updated)

        cnl.settings.appearence.line_color_changed.connect(
            lambda color, cnl=cnl: self._update_curve_style(cnl),
            self.Qt_DirConn,
        )
        cnl.settings.appearence.line_width_changed.connect(
            lambda width, cnl=cnl: self._update_curve_style(cnl),
            self.Qt_DirConn,
        )
        try:
            cnl.start()
        except Exception as e:
            print(str(e))
            self.remove_cnl(cnl)

    def remove_cnl(self, cnl):
        if curve := self.cnl_to_curve.pop(cnl, None):
            self.plot_widget.removeCurve(curve)
        cnl.stop()
        self.legend.remove_cnl(cnl)

    def shutdown(self):
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        if self._stats_timer:
            self._stats_timer.stop()
        if self._gc_timer:
            self._gc_timer.stop()

        for cnl in list(self.cnl_to_curve):
            self.remove_cnl(cnl)

        self._threadpool.waitForDone(5000)

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
                cnl = self.cnl_maker.create_cnl(sett)
                self.add_cnl(cnl)

    def _action_palette_triggered(self):
        conf = AlpineConfigurator(sett=self.settings)
        conf_dialog = ConfiguratorDialog(configurators={"Общее": conf})
        if conf_dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    def _action_pause_triggered(self):
        self.stop_flag = not self.stop_flag
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
        try:
            with open(self.settings_path, "r") as f:
                obj = json.load(f)
            self.settings: _AlpineSettings = AlpineSettings(**obj)  # type: ignore

            get_saving_trigger().triggered.connect(
                self._save_all_settings, self.Qt_DirConn
            )
            self.settings.time_range_changed.connect(
                self._on_time_range_changed,
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
        self._redraw_plot_hz = 0.0
        self._stats_timer = QTimer()
        self._stats_timer.setInterval(1000)  # раз в секунду
        self._stats_timer.timeout.connect(self._on_stats_timer)
        self._stats_timer.start()

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
            color = cnl.settings.appearence.line_color.value
            width = cnl.settings.appearence.line_width
            curve.setColor(color=color)
            curve.setWidth(width=width)

    def _on_time_range_changed(self, value):
        self.time_range = value

    def _on_x_axis_label_changed(self, value):
        self.plot_widget.set_x_axis_label(value)

    def _on_y_axis_label_changed(self, value):
        self.plot_widget.set_y_axis_label(value)

    def _save_all_settings(self):
        with open(self.settings_path, "w") as f:
            f.write(self.settings.model_dump_json(indent=2))

    ##########################
    #                        #
    #    timers callbacks    #
    #                        #
    ##########################

    def _on_stats_timer(self):
        if self._redraw_plot_count > 0:
            self._redraw_plot_hz = self._redraw_plot_count / 1.0  # за секунду
        else:
            self._redraw_plot_hz = 0.0
        self._redraw_plot_count = 0  # сброс счётчика

    def _on_gc_timer(self):
        collected = gc.collect()
        print(f"🧹 Сборщик мусора вызван (каждые 30 с), удалено объектов: {collected}")

    ###############################################
    #                                             #
    #    misc (but most intensitive) callbacks    #
    #                                             #
    ###############################################
    def _on_data_filtered(self, cnl, pos, to_dt):
        if self._is_shutting_down:
            return
        self._redraw_plot(cnl, pos, to_dt)

    def _on_cnl_updated(self, cnl):
        if self._is_shutting_down or cnl not in self.cnl_to_curve:
            return
        to_dt = datetime.now()
        from_dt = to_dt - self.time_range

        task = _FilterDataTask(self, cnl, from_dt, to_dt, self._on_data_filtered)
        self._threadpool.start(task, priority=0)

    def _redraw_plot(self, cnl, pos, to_dt):
        if self.stop_flag:
            return
        if curve := self.cnl_to_curve.get(cnl):
            self.plot_widget.set_x_axis_time_reference(to_dt)
            curve.setData(pos)
            self.plot_widget.autoRange()
            self._redraw_plot_count += 1

    Qt_DirConn = Qt.ConnectionType.DirectConnection
