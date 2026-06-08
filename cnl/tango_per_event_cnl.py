import time
from typing import Literal
from datetime import datetime
from collections.abc import Iterable

from pydantic import Field, BaseModel
from PySide6.QtCore import QThread, QObject, Signal, QTimer, Qt
from tango import DeviceProxy

from cnl.cnl import _ChannelSettings, _Channel
from aux.settings_decorators import with_settings_property, settings_with_signals


def is_scalar(value):
    return not isinstance(value, Iterable) or isinstance(value, (str, bytes, bytearray))


def normalize_attr_value(value):
    if is_scalar(value):
        return value
    try:
        if len(value) == 1:
            return value[0]
    except TypeError:
        pass
    return value


class TPESetupConfig(BaseModel):
    host: str = Field(default="")
    port: int = Field(default=10000)
    device_name: str = Field(default="пустой/девайс/000")
    attribute_name: str = Field(default="пустой_атрибут")
    polling_interval_msec: int = Field(default=1000)


TPESetupConfigWithSignals = settings_with_signals(TPESetupConfig)


class _TPEChannelSettings(_ChannelSettings):
    type: Literal["TPEChannelSettings"] = "TPEChannelSettings"
    setup_config: TPESetupConfig = Field(default_factory=TPESetupConfig)


TPEChannelSettings = settings_with_signals(_TPEChannelSettings)


########################
#                      #
#     _TPEWorker       #
#                      #
########################
class _TPEWorker(QObject):
    """Рабочий объект, живёт в отдельном потоке и содержит QTimer"""

    data_ready = Signal(object)
    error_occurred = Signal(str)
    connection_lost = Signal()
    metrics_updated = Signal(dict)

    def __init__(self, settings: TPESetupConfig):
        super().__init__()
        self.settings = settings
        self._device_proxy: DeviceProxy | None = None
        self._timer: QTimer | None = None
        self._is_running = False
        self._reconnect_attempts = 0

        self._poll_count = 0
        self._last_poll_time = 0
        self._response_times = []
        self._hz_history = []
        self._last_metrics_time = 0
        self._start_time = None

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._start_time = time.time()
        self._last_metrics_time = time.time()

        self._connect_device()
        if self._device_proxy is None:
            return

        _timer = QTimer()
        self._timer = _timer
        self._apply_polling_interval()
        _timer.timeout.connect(self._poll_device)
        _timer.start()

    def stop(self):
        self._is_running = False
        if _timer := self._timer:
            _timer.stop()
            _timer.deleteLater()
            _timer = None
        self._device_proxy = None

    def _connect_device(self):
        try:
            sts = self.settings
            if sts.host and sts.port:
                uri = f"tango://{sts.host}:{sts.port}/{sts.device_name}"
                _device_proxy = DeviceProxy(uri)
            else:
                _device_proxy = DeviceProxy(sts.device_name)
            self._device_proxy = _device_proxy
            _device_proxy.set_timeout_millis(3000)
            _device_proxy.ping()

            self._reconnect_attempts = 0
            print(f"Подключено к Tango устройству {sts.device_name}")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка подключения к Tango: {e}")
            self._device_proxy = None

    def _apply_polling_interval(self):
        if self._timer is None:
            return
        interval = max(1, int(self.settings.polling_interval_msec))
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    # @profile
    def _poll_device(self):
        if not self._is_running:
            return
        self._apply_polling_interval()

        poll_start = time.time()
        self._poll_count += 1

        current_hz = 0
        if self._last_poll_time > 0:
            interval = poll_start - self._last_poll_time
            current_hz = 1.0 / interval
            self._hz_history.append(current_hz)
            if len(self._hz_history) > 10:
                self._hz_history.pop(0)

        self._last_poll_time = poll_start

        if self._device_proxy is None:
            self._reconnect_attempts += 1
            if self._reconnect_attempts <= 3:
                print(f"Попытка переподключения {self._reconnect_attempts}/3...")
                self._connect_device()
            else:
                self.error_occurred.emit("Потеряно соединение с Tango устройством")
                self.connection_lost.emit()
                return

        if self._device_proxy is None:
            return

        try:
            attr_value = self._device_proxy.read_attribute(
                self.settings.attribute_name
            ).value  # type: ignore

            record = {
                "timestamp": datetime.now().timestamp(),
                "device": self.settings.device_name,
                "attribute": self.settings.attribute_name,
                "value": normalize_attr_value(attr_value),
            }

            self.data_ready.emit(record)
            self._reconnect_attempts = 0

            now = time.time()
            if now - self._last_metrics_time >= 1.0:
                self._last_metrics_time = now

        except Exception as e:
            self.error_occurred.emit(f"Ошибка чтения Tango атрибута: {e}")


########################
#                      #
#      _TPEThread      #
#                      #
########################
class _TPEThread(QThread):
    data_ready = Signal(object)
    error_occurred = Signal(str)
    connection_lost = Signal()
    metrics_updated = Signal(dict)

    def __init__(self, settings: TPESetupConfig):
        super().__init__()
        self.settings = settings
        self._worker: _TPEWorker | None = None

    # @profile
    def run(self):
        _worker = _TPEWorker(self.settings)
        self._worker = _worker
        _worker.moveToThread(self)

        _worker.data_ready.connect(self.data_ready)
        _worker.error_occurred.connect(self.error_occurred)
        _worker.connection_lost.connect(self.connection_lost)
        _worker.metrics_updated.connect(self.metrics_updated)

        _worker.start()
        self.exec_()

    def stop(self):
        if self._worker:
            self._worker.stop()
        self.quit()
        self.wait(5000)
        if self.isRunning():
            self.terminate()
            self.wait()


#######################
#                     #
#     TPEChannel      #
#                     #
#######################
@with_settings_property()
class TPEChannel(_Channel):
    # @profile
    def __init__(self, settings):
        super().__init__(settings)
        
        self._is_running = False

        self._polling_thread: _TPEThread | None = None

    # @profile
    def start(self):
        if self._is_running:
            print(f"{self.settings.name} уже запущен")
            return

        cfg = self.settings.setup_config._model

        try:
            _polling_thread = _TPEThread(cfg)
            self._polling_thread = _polling_thread
            _polling_thread.data_ready.connect(
                self._on_data_received, Qt.ConnectionType.QueuedConnection
            )
            _polling_thread.error_occurred.connect(
                self._on_error, Qt.ConnectionType.QueuedConnection
            )
            _polling_thread.connection_lost.connect(
                self._on_connection_lost, Qt.ConnectionType.QueuedConnection
            )
            _polling_thread.finished.connect(
                self._on_thread_finished, Qt.ConnectionType.QueuedConnection
            )

            _polling_thread.start()
            _polling_thread.setPriority(QThread.Priority.LowPriority)

            self._is_running = True

            print(
                f"{self.settings.name} запущен (опрос в отдельном потоке, {cfg.polling_interval_msec} мс)"
            )

        except Exception as e:
            print(f"{self.settings.name} ошибка запуска: {e}")
            self._is_running = False
            self.error_occurred.emit(str(e))

    def stop(self):
        if not self._is_running:
            return
        self._is_running = False

        if _polling_thread := self._polling_thread:
            _polling_thread.stop()
            self._polling_thread = None

        self.stopped.emit()
        print(f"{self.settings.name} остановлен")

    # @profile
    def _on_data_received(self, record):
        self.register_poll_timing(record)
        self.new_data = record
        self.data.append(record)
        self.updated.emit(self)

    def _on_error(self, error_msg):
        print(f"{self.settings.name} ошибка: {error_msg}")
        self.error_occurred.emit(error_msg)

    def _on_connection_lost(self):
        print(f"{self.settings.name} потеряно соединение с Tango устройством")

    def _on_thread_finished(self):
        print(f"{self.settings.name} поток опроса завершён")
