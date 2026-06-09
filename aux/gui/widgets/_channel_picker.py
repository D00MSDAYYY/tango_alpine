from typing import Protocol


class _ChannelPicker(Protocol):
    def pick_channels(self, channel_settings, existing_channels) -> list:
        ...
