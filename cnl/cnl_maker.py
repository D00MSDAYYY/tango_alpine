from cnl.cnl import _Channel
from cnl.error_cnl import ErrorChannel
from cnl.modbus_cnl import ModbusChannelSettings, ModbusChannel
from cnl.tango_per_event_cnl import TPEChannelSettings, TPEChannel
from cnl.dummy_printer_cnl import DummyChannelSettings, DummyChannel


class ChannelMaker:
    def __init__(self, app):
        self.app = app
        self.cnl_classes = {
            TPEChannelSettings: TPEChannel,
            ModbusChannelSettings: ModbusChannel,
            DummyChannelSettings: DummyChannel,
        }
        self.fallback_cnl_class = _Channel

    def create_cnl(self, cnl_sett):
        cnl_class = self.cnl_classes.get(type(cnl_sett), self.fallback_cnl_class)

        cnl = cnl_class(cnl_sett)

        return cnl

    def create_error_cnl(self, cnl_sett, error_text):
        return ErrorChannel(cnl_sett, error_text)
