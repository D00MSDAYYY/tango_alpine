from typing import Literal

from pydantic import BaseModel, Field

from aux.gui.enums import LineColor, random_line_color
from aux.settings._polymorphic import PolymorphicBase
from aux.settings.decorators import settings_with_signals


class _Appearence(BaseModel):
    line_width: float = Field(default=1.0)
    line_color: LineColor = Field(default_factory=random_line_color)  # type: ignore
    show_dots: bool = Field(default=False)


Appearence = settings_with_signals(_Appearence)


class _ChannelSettings(PolymorphicBase):
    type: Literal["ChannelSettings"] = "ChannelSettings"
    name: str = Field(default="безымянный_канал")
    units: str | None = Field(default=None)

    appearence: _Appearence = Field(default_factory=_Appearence)


ChannelSettings = settings_with_signals(_ChannelSettings)
