import math
import time
import traceback
from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from PySide6.QtCore import Signal, QThread, QObject

from cnl.cnl import _ChannelSettings, _Channel
from aux.settings_decorators import with_settings_property, settings_with_signals


class SineWorker(QObject):
    data_ready = Signal(object)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, setup_config):
        super().__init__()
        self._setup_config = setup_config
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        try:
            start_monotonic = time.monotonic()
            start_timestamp = datetime.now().timestamp()
            initial_interval_sec = max(
                0.001,
                int(self._setup_config.polling_interval_msec) / 1000.0,
            )
            angular_speed = 0.1 / initial_interval_sec
            while not self._stop_flag:
                elapsed = time.monotonic() - start_monotonic
                timestamp = start_timestamp + elapsed
                value = math.sin(elapsed * angular_speed)
                record = {
                    "timestamp": timestamp,
                    "value": value,
                }
                self.data_ready.emit(record)
                interval = int(self._setup_config.polling_interval_msec)
                QThread.msleep(max(1, interval))
        except Exception:
            self.error_occurred.emit(traceback.format_exc())
        finally:
            self.finished.emit()


class DummyChannelSetupConfig(BaseModel):
    polling_interval_msec: int = Field(default=10)


DummyChannelSetupConfigWithSignals = settings_with_signals(DummyChannelSetupConfig)


class _DummyChannelSettings(_ChannelSettings):
    type: Literal["DummyChannelSettings"] = "DummyChannelSettings"  # type: ignore
    setup_config: DummyChannelSetupConfig = Field(
        default_factory=DummyChannelSetupConfig
    )


DummyChannelSettings = settings_with_signals(_DummyChannelSettings)


@with_settings_property()
class DummyChannel(_Channel):
    def __init__(self, settings):
        super().__init__(settings)
        self._thread = None
        self._worker = None
        self._is_running = False

    def start(self):
        if self._is_running:
            return
        try:
            cfg = self.settings.setup_config._model
            self._thread = QThread()
            self._worker = SineWorker(cfg)
            self._worker.moveToThread(self._thread)

            self._thread.started.connect(self._worker.run)
            self._worker.data_ready.connect(self._on_data_received)
            self._worker.error_occurred.connect(self._on_error)
            self._worker.finished.connect(self._thread.quit)

            self._thread.start()
            self._is_running = True
            print(
                f"{self.settings.name} запущен (dummy, {cfg.polling_interval_msec} мс)"
            )
        except Exception:
            self._is_running = False
            self.error_occurred.emit(traceback.format_exc())

    def stop(self):
        if not self._is_running:
            return
        self._is_running = False
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(5000):
                self._thread.terminate()
                self._thread.wait()
        self._worker = None
        self._thread = None
        self.stopped.emit()
        print(f"{self.settings.name} остановлен")

    def _on_data_received(self, record):
        self.register_poll_timing(record)
        self.new_data = record
        self.data.append(record)
        self.updated.emit(self)

    def _on_error(self, error_text):
        print(f"{self.settings.name} ошибка: {error_text}")
        self.error_occurred.emit(error_text)
