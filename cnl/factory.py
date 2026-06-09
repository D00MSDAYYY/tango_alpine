from cnl._base import _Channel
from cnl._channel import _ChannelProtocol
from cnl._settings import _ChannelSettings
from cnl.error_cnl import ErrorChannel
from cnl.modbus_cnl import ModbusChannelSettings, ModbusChannel
from cnl.tango_per_event_cnl import TPEChannelSettings, TPEChannel
from cnl.dummy_printer_cnl import DummyChannelSettings, DummyChannel


class ChannelFactory:
    def __init__(self, appearance_dialog_factory):
        self.appearance_dialog_factory = appearance_dialog_factory
        self.cnl_classes = {
            TPEChannelSettings: TPEChannel,
            ModbusChannelSettings: ModbusChannel,
            DummyChannelSettings: DummyChannel,
        }
        self.fallback_cnl_class = _Channel

    def create_channel(self, cnl_sett: _ChannelSettings) -> _ChannelProtocol:
        cnl_class = self.cnl_classes.get(type(cnl_sett), self.fallback_cnl_class)

        cnl = cnl_class(cnl_sett, self.appearance_dialog_factory)

        return cnl

    def create_error_channel(
        self,
        cnl_sett: _ChannelSettings,
        error_text: str,
    ) -> _ChannelProtocol:
        return ErrorChannel(cnl_sett, error_text, self.appearance_dialog_factory)
