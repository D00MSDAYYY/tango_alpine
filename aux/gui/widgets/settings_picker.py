import os

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QDialogButtonBox,
)


class SettingsPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected_file_path = None
        self.valid_extensions = [".xlsx", ".json"]
        self.setWindowTitle("Выберите файл конфигурации")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header_label = QLabel("Пожалуйста, укажите путь до файла конфигурации:")
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setText("./resources/config.xlsx")
        file_layout.addWidget(self.file_path_edit)

        self.browse_button = QPushButton("Найти...")
        self.browse_button.setFixedWidth(100)
        file_layout.addWidget(self.browse_button)
        layout.addLayout(file_layout)

        formats_label = QLabel("Поддерживаемые форматы: .xlsx, .json")
        layout.addWidget(formats_label)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Сохраняем ссылку на кнопку OK для удобства
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)

        self._validate_file_path(self.file_path_edit.text())

    def _connect_signals(self):
        self.file_path_edit.textChanged.connect(self._validate_file_path)
        self.browse_button.clicked.connect(self._browse_file)
        self.button_box.accepted.connect(self._on_ok_clicked)
        self.button_box.rejected.connect(self.reject)

    def _validate_file_path(self, file_path):
        if not file_path:
            self.ok_button.setEnabled(False)
            self.status_label.setText("")
            return False

        if os.path.exists(file_path) and os.path.isfile(file_path):
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in self.valid_extensions:
                self.ok_button.setEnabled(True)
                self.status_label.setText("✅ Файл найден")
                self.status_label.setStyleSheet("color: green;")
                return True
            else:
                self.ok_button.setEnabled(False)
                self.status_label.setText("❌ Неподдерживаемый формат")
                self.status_label.setStyleSheet("color: red;")
                return False
        else:
            self.ok_button.setEnabled(False)
            self.status_label.setText("❌ Файл не существует")
            self.status_label.setStyleSheet("color: red;")
            return False

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл конфигурации",
            "",
            "Файл конфигурации (*.xlsx *.json)",
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def _on_ok_clicked(self):
        file_path = self.file_path_edit.text()
        if self._validate_file_path(file_path):
            self.selected_file_path = file_path
            self.accept()

    def get_file_path(self):
        return self.selected_file_path
