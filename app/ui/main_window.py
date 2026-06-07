"""Main application window: a left navigation rail (Chat / Models / Settings) over a stacked content area."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout, QWidget,
)

from app.backends.registry import BackendRegistry
from app.core.settings import AppSettings
from app.ui.chat_page import ChatPage
from app.ui.models_page import ModelsPage
from app.ui.settings_page import SettingsPage

NAV_ITEMS = [
    ("chat", "💬  Chat"),
    ("models", "📦  Models"),
    ("settings", "⚙️  Settings"),
]


class MainWindow(QWidget):
    def __init__(self, icon: QIcon | None = None):
        super().__init__()
        self.setWindowTitle("Local AI Assistant")
        self.resize(1180, 760)
        if icon is not None:
            self.setWindowIcon(icon)

        self._settings = AppSettings()
        self._registry = BackendRegistry()
        for entry in self._settings.custom_backends:
            display_name = entry.get("display_name", "")
            base_url = entry.get("base_url", "")
            if display_name and base_url:
                self._registry.add_openai_compatible(display_name, base_url)

        # Build the content stack first — the nav rail's selection signal fires
        # immediately on construction and needs `_stack` to already exist.
        self._stack = QStackedWidget()
        self._chat_page = ChatPage(self._registry, self._settings)
        self._models_page = ModelsPage(self._registry)
        self._settings_page = SettingsPage(self._registry, self._settings)
        self._settings_page.backends_changed.connect(self._on_backends_changed)

        self._stack.addWidget(self._chat_page)
        self._stack.addWidget(self._models_page)
        self._stack.addWidget(self._settings_page)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav_rail())
        root.addWidget(self._stack, 1)

    # ------------------------------------------------------------------
    def _build_nav_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("navRail")
        rail.setFixedWidth(180)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(4)

        title = QLabel("Local AI")
        title.setObjectName("appTitle")
        layout.addWidget(title)
        subtitle = QLabel("Your private coding assistant")
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        self._nav_list = QListWidget()
        self._nav_list.setObjectName("navList")
        self._nav_list.setFrameShape(QFrame.NoFrame)
        for key, label in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self._nav_list.addItem(item)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        self._nav_list.setCurrentRow(0)
        layout.addWidget(self._nav_list, 1)
        return rail

    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)
        if NAV_ITEMS[row][0] == "models":
            self._models_page.refresh()

    def _on_backends_changed(self) -> None:
        self._chat_page.refresh_backends()
        self._models_page.refresh_backends()
