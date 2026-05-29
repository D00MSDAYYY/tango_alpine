from PySide6.QtWidgets import QApplication, QDialog

from aux.gui import resources_rc  # noqa: F401
from alpine import Alpine
from aux.gui.widgets.settings_picker import SettingsPicker


def main():
    app = QApplication()
    font = app.font()
    if font.pointSize() > 0:
        font.setPointSize(round(font.pointSize() * 1.2))
    elif font.pixelSize() > 0:
        font.setPixelSize(round(font.pixelSize() * 1.2))
    app.setFont(font)

    settings_picker = SettingsPicker()

    if settings_picker.exec() == QDialog.DialogCode.Accepted:
        alpine = Alpine(settings_picker.get_file_path())
        app.aboutToQuit.connect(alpine.shutdown)
        alpine.show()
    del settings_picker

    app.exec()


if __name__ == "__main__":
    main()
