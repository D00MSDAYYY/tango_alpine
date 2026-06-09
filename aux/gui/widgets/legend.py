from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QWidget,
    QVBoxLayout,
    QScrollArea,
)


class LegendWidget(QWidget):
    MIN_EXPANDED_WIDTH = 260

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        self.scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        self.container = container
        container.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

        _layout = QVBoxLayout(container)
        self._layout = _layout
        _layout.setContentsMargins(0, 0, 0, 0)
        _layout.setSpacing(5)
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
