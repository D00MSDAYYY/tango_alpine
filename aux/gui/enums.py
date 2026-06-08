from enum import Enum
import random
from vispy.color import get_color_names

def _line_color_member_name(color_name):
    return color_name.replace(" ", "_").replace("-", "_").upper()


LineColor = Enum(
    "LineColor",
    {_line_color_member_name(color_name): color_name for color_name in get_color_names()},
)


def random_line_color():
    return random.choice(list(LineColor))
