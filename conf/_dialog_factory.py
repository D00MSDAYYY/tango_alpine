from typing import Protocol

from PySide6.QtWidgets import QDialog


class _SettingsDialogFactory(Protocol):
    def create_settings_dialog(self, settings) -> QDialog:
        ...
