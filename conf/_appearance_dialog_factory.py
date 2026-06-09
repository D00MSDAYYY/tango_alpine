from typing import Protocol

from PySide6.QtWidgets import QDialog


class _AppearanceDialogFactory(Protocol):
    def create_appearance_dialog(self, appearance_settings) -> QDialog:
        ...
