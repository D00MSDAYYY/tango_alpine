from typing import Protocol

from cnl._channel import _ChannelProtocol
from cnl._settings import _ChannelSettings


class _ChannelFactory(Protocol):
    def create_channel(self, cnl_sett: _ChannelSettings) -> _ChannelProtocol:
        ...

    def create_error_channel(
        self,
        cnl_sett: _ChannelSettings,
        error_text: str,
    ) -> _ChannelProtocol:
        ...
