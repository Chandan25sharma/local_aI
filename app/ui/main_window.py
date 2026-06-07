"""Main application window: one merged, collapsible sidebar (app identity, New-chat,
page navigation, and recent-chat history — Claude-style) over a stacked content area."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.backends.registry import BackendRegistry
from app.core.chat_session import list_sessions
from app.core.settings import AppSettings
from app.ui.chat_page import ChatPage
from app.ui.models_page import ModelsPage
from app.ui.settings_page import SettingsPage

NAV_ITEMS = [
    ("chat", "💬  Chat"),
    ("models", "📦  Models"),
    ("settings", "⚙️  Settings"),
]

_EXPANDED_WIDTH = 248
_COLLAPSED_WIDTH = 56


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

        # Build the content stack first — the nav list's selection signal fires
        # immediately on construction and needs `_stack` to already exist.
        self._stack = QStackedWidget()
        self._chat_page = ChatPage(self._registry, self._settings)
        self._models_page = ModelsPage(self._registry)
        self._settings_page = SettingsPage(self._registry, self._settings)
        self._chat_page.sessions_changed.connect(self._refresh_session_list)
        self._settings_page.backends_changed.connect(self._on_backends_changed)

        self._stack.addWidget(self._chat_page)
        self._stack.addWidget(self._models_page)
        self._stack.addWidget(self._settings_page)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._stack, 1)

        self._refresh_session_list()

    # ------------------------------------------------------------------
    # The merged sidebar — identity + collapse toggle, New chat, page nav,
    # and recent-chat history, all in one panel that opens/closes as a unit.
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        self._sidebar = QFrame()
        self._sidebar.setObjectName("navRail")
        self._sidebar.setFixedWidth(_EXPANDED_WIDTH)
        outer = QVBoxLayout(self._sidebar)
        outer.setContentsMargins(10, 14, 10, 14)
        outer.setSpacing(8)

        toggle_row = QHBoxLayout()
        self._sidebar_toggle_btn = QPushButton("☰")
        self._sidebar_toggle_btn.setObjectName("iconBtn")
        self._sidebar_toggle_btn.setFixedSize(30, 30)
        self._sidebar_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._sidebar_toggle_btn.setToolTip("Collapse sidebar")
        self._sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        toggle_row.addWidget(self._sidebar_toggle_btn)
        toggle_row.addStretch(1)
        outer.addLayout(toggle_row)

        # Everything below the toggle collapses/expands together as one body,
        # leaving just the slim toggle rail visible when closed.
        self._sidebar_body = QWidget()
        body = QVBoxLayout(self._sidebar_body)
        body.setContentsMargins(4, 0, 4, 0)
        body.setSpacing(8)

        title = QLabel("Local AI")
        title.setObjectName("appTitle")
        body.addWidget(title)
        subtitle = QLabel("Your private coding assistant")
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)
        body.addSpacing(6)

        new_chat_btn = QPushButton("＋  New chat")
        new_chat_btn.setObjectName("primaryBtn")
        new_chat_btn.setCursor(Qt.PointingHandCursor)
        new_chat_btn.clicked.connect(self._on_new_chat_clicked)
        body.addWidget(new_chat_btn)

        self._nav_list = QListWidget()
        self._nav_list.setObjectName("navList")
        self._nav_list.setFrameShape(QFrame.NoFrame)
        for key, label in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self._nav_list.addItem(item)
        self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_list.setMaximumHeight(len(NAV_ITEMS) * 46 + 12)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        self._nav_list.setCurrentRow(0)
        body.addWidget(self._nav_list)

        recent_label = QLabel("RECENT CHATS")
        recent_label.setObjectName("appSubtitle")
        body.addWidget(recent_label)

        self._session_list = QListWidget()
        self._session_list.setObjectName("sessionList")
        self._session_list.setFrameShape(QFrame.NoFrame)
        self._session_list.itemClicked.connect(self._on_session_clicked)
        body.addWidget(self._session_list, 1)

        outer.addWidget(self._sidebar_body, 1)
        return self._sidebar

    def _toggle_sidebar(self) -> None:
        expanded = self._sidebar_body.isVisible()
        self._sidebar_body.setVisible(not expanded)
        self._sidebar.setFixedWidth(_COLLAPSED_WIDTH if expanded else _EXPANDED_WIDTH)
        self._sidebar_toggle_btn.setToolTip("Show sidebar" if expanded else "Collapse sidebar")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)
        if NAV_ITEMS[row][0] == "models":
            self._models_page.refresh()

    def _on_backends_changed(self) -> None:
        self._chat_page.refresh_backends()
        self._models_page.refresh_backends()

    # ------------------------------------------------------------------
    # Chat history — New chat button + recent-chats list
    # ------------------------------------------------------------------
    def _on_new_chat_clicked(self) -> None:
        self._nav_list.setCurrentRow(0)
        self._session_list.setCurrentRow(-1)
        self._chat_page.start_new_chat()

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.UserRole)
        for session in list_sessions():
            if session.id == session_id:
                self._nav_list.setCurrentRow(0)
                self._chat_page.load_session(session)
                return

    def _refresh_session_list(self) -> None:
        current_id = self._chat_page.current_session_id
        self._session_list.blockSignals(True)
        self._session_list.clear()
        for session in list_sessions():
            item = QListWidgetItem(session.title or "New chat")
            item.setData(Qt.UserRole, session.id)
            self._session_list.addItem(item)
            if session.id == current_id:
                self._session_list.setCurrentItem(item)
        self._session_list.blockSignals(False)
