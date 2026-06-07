"""One row in the Models page list — name, size, last-modified, and a delete action."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from app.backends.base import ModelInfo


class ModelRow(QFrame):
    delete_requested = Signal(str)

    def __init__(self, model: ModelInfo, deletable: bool, parent=None):
        super().__init__(parent)
        self.model_name = model.name
        self.setObjectName("modelRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        name = QLabel(model.name)
        name.setObjectName("modelName")
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(name)

        if model.size_bytes:
            size_label = QLabel(model.size_human)
            size_label.setObjectName("modelMeta")
            layout.addWidget(size_label)

        if model.modified_at:
            modified = QLabel(model.modified_at.split("T")[0])
            modified.setObjectName("modelMeta")
            layout.addWidget(modified)

        if deletable:
            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("dangerBtn")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.model_name))
            layout.addWidget(delete_btn)
