import math
from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from PySide6.QtCore import Signal, QThread, QObject

from cnl.cnl import _ChannelSettings, _Channel
from aux.settings_decorators import with_settings_property, settings_with_signals


class SineWorker(QObject):
    data_ready = Signal(object)

    def __init__(self, channel):
        super().__init__()
        self._channel = channel
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        angle = 0.0
        step = 0.1
        while not self._stop_flag:
            # Генерация синуса
            value = math.sin(angle)
            record = {
                "timestamp": datetime.now().timestamp(),
                "value": value,
            }
            self.data_ready.emit(record)
            angle += step
            QThread.msleep(self._channel.settings.setup_config.polling_interval_msec)


class DummyChannelSetupConfig(BaseModel):
    polling_interval_msec: int = Field(default=10)


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
        self._thread = QThread()
        self._thread.setPriority(QThread.Priority.LowPriority)
        self._worker = SineWorker(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.data_ready.connect(self._on_data_received)

        self._thread.start()
        self._is_running = True

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

    def _on_data_received(self, record):
        self.new_data = record
        self.data.append(record)
        self.updated.emit(self)
