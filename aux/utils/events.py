from PySide6.QtCore import QEvent


class ClickEvent(QEvent):
    def __init__(self):
        super().__init__(QEvent.Type(QEvent.Type.User + 1))
