import time
import struct
from enum import Enum
from datetime import datetime
from typing import Literal
from pydantic import Field, BaseModel

from pymodbus.client import ModbusTcpClient
from PySide6.QtCore import QTimer, QThread, QObject, Signal

from cnl.cnl import _Channel, _ChannelSettings
from aux.settings_decorators import with_settings_property
from aux.settings_decorators import settings_with_signals


class ModbusRegisterType(str, Enum):
    holding = "holding"
    input = "input"


class ModbusDataType(str, Enum):
    float32 = "float32"


class ModbusSetupConfig(BaseModel):
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=502)
    modbus_id: int = Field(default=1)

    register_type: ModbusRegisterType = Field(default=ModbusRegisterType.holding)
    register_address: int = Field(default=0)
    data_type: ModbusDataType = Field(default=ModbusDataType.float32)

    polling_interval_msec: int = Field(default=1000)
    byte_order: str = Field(default="little")   
    word_order: str = Field(default="big")      


class _ModbusChannelSettings(_ChannelSettings):
    type: Literal["ModbusChannelSettings"] = "ModbusChannelSettings"
    setup_config: ModbusSetupConfig = Field(default_factory=ModbusSetupConfig)


ModbusChannelSettings = settings_with_signals(_ModbusChannelSettings)


def convert_float32(high: int, low: int, byte_order: str, word_order: str) -> float:
    """
    Конвертирует два 16-битных регистра в float32 с заданным порядком байтов и слов.
    byte_order: 'big' или 'little' – порядок байтов внутри 32-битного числа.
    word_order: 'big' – первый регистр – старшие 16 бит, второй – младшие;
                 'little' – первый – младшие, второй – старшие.
    """
    if word_order == 'big':
        w1, w2 = high, low
    else:
        w1, w2 = low, high

    combined = (w1 << 16) | w2

    if byte_order == 'big':
        return struct.unpack('>f', struct.pack('>I', combined))[0]
    else:
        return struct.unpack('<f', struct.pack('<I', combined))[0]


########################
#                      #
#    _PollingWorker    #
#                      #
########################
class _PollingWorker(QObject):
    data_ready = Signal(object)
    error_occurred = Signal(str)
    connection_lost = Signal()
    metrics_updated = Signal(dict)

    def __init__(self, settings: ModbusSetupConfig):
        super().__init__()
        self.settings = settings
        self._client: ModbusTcpClient | None = None
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

        self._connect_client()
        self._timer = QTimer()
        self._timer.setInterval(self.settings.polling_interval_msec)
        self._timer.timeout.connect(self._poll_device)
        self._timer.start()

        self._poll_device()

    def stop(self):
        self._is_running = False
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._client:
            self._client.close()
            self._client = None

    def _connect_client(self):
        try:
            self._client = ModbusTcpClient(self.settings.host, port=self.settings.port)
            if not self._client.connect():
                self.error_occurred.emit(
                    f"Не удалось подключиться к {self.settings.host}:{self.settings.port}"
                )
                self._client = None
                return
            self._reconnect_attempts = 0
            print(f"Подключено к {self.settings.host}:{self.settings.port}")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка подключения: {e}")
            self._client = None

    def _poll_device(self):
        if not self._is_running:
            return

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

        if self._client is None or not self._client.connected:
            self._reconnect_attempts += 1
            if self._reconnect_attempts <= 3:
                print(f"Попытка переподключения {self._reconnect_attempts}/3...")
                self._connect_client()
            else:
                self.error_occurred.emit("Потеряно соединение с устройством")
                self.connection_lost.emit()
                return

        if self._client is None or not self._client.connected:
            return

        cfg = self.settings
        try:
            if cfg.register_type == "holding":
                if cfg.data_type == "float32":
                    result = self._client.read_holding_registers(
                        address=cfg.register_address, count=2, device_id=cfg.modbus_id
                    )
                else:
                    result = self._client.read_holding_registers(
                        address=cfg.register_address, count=1, device_id=cfg.modbus_id
                    )
            else:  # input
                if cfg.data_type == "float32":
                    result = self._client.read_input_registers(
                        address=cfg.register_address, count=2, device_id=cfg.modbus_id
                    )
                else:
                    result = self._client.read_input_registers(
                        address=cfg.register_address, count=1, device_id=cfg.modbus_id
                    )

            if result.isError():
                self.error_occurred.emit(f"Ошибка Modbus: {result}")
                return

            registers = result.registers

            if cfg.data_type == "float32":
                if len(registers) < 2:
                    self.error_occurred.emit("Для float32 нужно 2 регистра")
                    return
                high, low = registers[0], registers[1]
                value = convert_float32(high, low, cfg.byte_order, cfg.word_order)
            else:
                value = registers[0] if registers else None

            record = {
                "timestamp": datetime.now().timestamp(),
                "device": f"{cfg.host}:{cfg.port}:{cfg.modbus_id}",
                "attribute": f"{cfg.register_type}_{cfg.register_address}",
                "value": value,
            }

            self.data_ready.emit(record)
            self._reconnect_attempts = 0

            now = time.time()
            if now - self._last_metrics_time >= 1.0:
                # Здесь можно вызывать self._send_metrics(current_hz) при необходимости
                self._last_metrics_time = now

        except Exception as e:
            self.error_occurred.emit(f"Ошибка опроса: {e}")


########################
#                      #
#    _PollingThread    #
#                      #
########################
class _PollingThread(QThread):
    data_ready = Signal(object)
    error_occurred = Signal(str)
    connection_lost = Signal()

    def __init__(self, settings: ModbusSetupConfig):
        super().__init__()
        self.settings = settings
        self._worker: _PollingWorker | None = None

    def run(self):
        self._worker = _PollingWorker(self.settings)
        self._worker.moveToThread(self)
        self._worker.data_ready.connect(self.data_ready)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.connection_lost.connect(self.connection_lost)
        self._worker.start()
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
#    ModbusChannel    #
#                     #
#######################
@with_settings_property()
class ModbusChannel(_Channel):
    def __init__(self, settings):
        super().__init__(settings)
        self._polling_thread: _PollingThread | None = None
        self._is_running = False
        self._update_timer: QTimer | None = None
        self._pending_record = None   # для ограничения частоты GUI

    def start(self):
        if self._is_running:
            print(f"{self.settings.name} уже запущен")
            return

        cfg = self.settings.setup_config

        try:
            self._polling_thread = _PollingThread(cfg)

            self._polling_thread.data_ready.connect(self._on_data_received)
            self._polling_thread.error_occurred.connect(self._on_error)
            self._polling_thread.connection_lost.connect(self._on_connection_lost)
            self._polling_thread.finished.connect(self._on_thread_finished)

            # Таймер ограничения частоты обновления GUI (не чаще 20 раз в секунду)
            gui_update_interval = min(cfg.polling_interval_msec, 50)
            self._update_timer = QTimer()
            self._update_timer.setInterval(gui_update_interval)
            self._update_timer.timeout.connect(self._update_gui)
            self._update_timer.start()

            self._polling_thread.start()
            self._polling_thread.setPriority(QThread.Priority.LowPriority)

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
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer.deleteLater()
            self._update_timer = None
        if self._polling_thread:
            self._polling_thread.stop()
            self._polling_thread = None
        self.stopped.emit()
        print(f"{self.settings.name} остановлен")

    def _on_data_received(self, record):
        self.data.append(record)
        self._pending_record = record   # сохраняем для отложенной отправки

    def _update_gui(self):
        """Вызывается таймером для ограничения частоты обновления GUI"""
        if self._pending_record is not None:
            self.new_data = self._pending_record
            self.updated.emit(self)
            self._pending_record = None

    def _on_error(self, error_msg):
        print(f"{self.settings.name} ошибка: {error_msg}")
        self.error_occurred.emit(error_msg)

    def _on_connection_lost(self):
        print(f"{self.settings.name} потеряно соединение с устройством")

    def _on_thread_finished(self):
        print(f"{self.settings.name} поток опроса завершён")
