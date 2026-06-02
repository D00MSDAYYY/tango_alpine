from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea


class LegendWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        self.scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        self.container = container

        _layout = QVBoxLayout(container)
        self._layout = _layout  
        _layout.setContentsMargins(3, 3, 3, 3)
        _layout.setSpacing(3)
        _layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def add_cnl(self, cnl_v):
        self._layout.addWidget(cnl_v)

    def remove_cnl(self, cnl):
        self._layout.removeWidget(cnl)
        cnl.deleteLater()

    def clear(self):
        while self._layout.count():
            if item := self._layout.takeAt(0):
                if wgt := item.widget():
                    wgt.deleteLater()


    def get_channels(self):
        widgets = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), "settings"):
                widgets.append(item.widget())
        return widgets
