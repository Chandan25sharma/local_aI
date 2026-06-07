"""Settings page: theme, default persona, and managing extra OpenAI-compatible backends
(LM Studio, llama.cpp server, vLLM, ...) so the app can talk to more than just Ollama."""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from app.backends.openai_compatible_backend import OpenAICompatibleBackend
from app.backends.registry import OPENAI_COMPATIBLE_PRESETS, BackendRegistry
from app.core.chat_session import sessions_dir
from app.core.settings import PERSONA_PRESETS, AppSettings


class SettingsPage(QWidget):
    backends_changed = Signal()

    def __init__(self, registry: BackendRegistry, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._settings = settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(18)
        outer.addWidget(self._build_general_section())
        outer.addWidget(self._build_backends_section())
        outer.addWidget(self._build_history_section())
        outer.addStretch(1)

    # ------------------------------------------------------------------
    def _section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("settingsSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        return frame, layout

    def _build_general_section(self) -> QWidget:
        frame, layout = self._section("General")

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self._theme_selector = QComboBox()
        self._theme_selector.addItems(["dark", "light"])
        self._theme_selector.setCurrentText(self._settings.theme)
        self._theme_selector.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_selector)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)

        persona_row = QHBoxLayout()
        persona_row.addWidget(QLabel("Default persona:"))
        self._persona_selector = QComboBox()
        self._persona_selector.addItems(list(PERSONA_PRESETS.keys()))
        self._persona_selector.setCurrentText(self._settings.persona)
        self._persona_selector.currentTextChanged.connect(self._on_persona_changed)
        persona_row.addWidget(self._persona_selector)
        persona_row.addStretch(1)
        layout.addLayout(persona_row)

        return frame

    def _on_theme_changed(self, value: str) -> None:
        self._settings.theme = value
        QMessageBox.information(self, "Theme", "Restart the app for the new theme to fully apply.")

    def _on_persona_changed(self, value: str) -> None:
        self._settings.persona = value

    # ------------------------------------------------------------------
    def _build_backends_section(self) -> QWidget:
        frame, layout = self._section("Local LLM backends")

        note = QLabel(
            "Ollama is always available as the default backend. You can also connect any server "
            "that exposes an OpenAI-compatible API — e.g. LM Studio or llama.cpp's built-in server."
        )
        note.setWordWrap(True)
        note.setObjectName("modelMeta")
        layout.addWidget(note)

        self._backend_list = QListWidget()
        self._backend_list.setObjectName("backendList")
        self._backend_list.setMaximumHeight(120)
        layout.addWidget(self._backend_list)

        remove_row = QHBoxLayout()
        remove_row.addStretch(1)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.setObjectName("dangerBtn")
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        remove_row.addWidget(self._remove_btn)
        layout.addLayout(remove_row)

        layout.addWidget(QLabel("Add a backend:"))
        form_row = QHBoxLayout()
        self._preset_selector = QComboBox()
        self._preset_selector.addItem("Custom…", None)
        for label, url in OPENAI_COMPATIBLE_PRESETS:
            self._preset_selector.addItem(label, url)
        self._preset_selector.currentIndexChanged.connect(self._on_preset_selected)
        form_row.addWidget(self._preset_selector)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Display name (e.g. LM Studio)")
        form_row.addWidget(self._name_input, 1)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Base URL (e.g. http://localhost:1234/v1)")
        form_row.addWidget(self._url_input, 1)

        add_btn = QPushButton("Add")
        add_btn.setObjectName("primaryBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_clicked)
        form_row.addWidget(add_btn)
        layout.addLayout(form_row)

        self._refresh_backend_list()
        return frame

    def _on_preset_selected(self, index: int) -> None:
        url = self._preset_selector.currentData()
        if url:
            self._name_input.setText(self._preset_selector.currentText())
            self._url_input.setText(url)
        else:
            self._name_input.clear()
            self._url_input.clear()

    def _refresh_backend_list(self) -> None:
        self._backend_list.clear()
        for backend in self._registry.backends:
            removable = backend.name == "openai_compatible"
            label = backend.display_name if not removable else f"{backend.display_name} — {backend.base_url}"
            item = QListWidgetItem(label + ("" if removable else "  (built-in)"))
            item.setData(Qt.UserRole, backend)
            self._backend_list.addItem(item)

    def _on_add_clicked(self) -> None:
        name = self._name_input.text().strip()
        url = self._url_input.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Missing details", "Please provide both a display name and a base URL.")
            return
        self._registry.add_openai_compatible(name, url)
        self._persist_custom_backends()
        self._name_input.clear()
        self._url_input.clear()
        self._preset_selector.setCurrentIndex(0)
        self._refresh_backend_list()
        self.backends_changed.emit()

    def _on_remove_clicked(self) -> None:
        item = self._backend_list.currentItem()
        if item is None:
            return
        backend = item.data(Qt.UserRole)
        if not isinstance(backend, OpenAICompatibleBackend):
            QMessageBox.information(self, "Built-in backend", "Ollama is built in and can't be removed.")
            return
        self._registry.remove(backend)
        self._persist_custom_backends()
        self._refresh_backend_list()
        self.backends_changed.emit()

    # ------------------------------------------------------------------
    def _build_history_section(self) -> QWidget:
        frame, layout = self._section("Chat history")

        note = QLabel(
            "Every conversation is saved automatically as its own file on this PC the moment "
            "you send a message — nothing is sent anywhere else. Each file holds the full back-and-forth, "
            "so the assistant always has your prior messages as context for that chat. "
            "Pick any past conversation up again from the list on the left of the Chat page."
        )
        note.setWordWrap(True)
        note.setObjectName("modelMeta")
        layout.addWidget(note)

        path_row = QHBoxLayout()
        path_label = QLabel(str(sessions_dir()))
        path_label.setObjectName("modelMeta")
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_row.addWidget(path_label, 1)
        open_btn = QPushButton("Open folder")
        open_btn.setObjectName("primaryBtn")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self._on_open_history_folder)
        path_row.addWidget(open_btn)
        layout.addLayout(path_row)

        return frame

    def _on_open_history_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(sessions_dir())))

    def _persist_custom_backends(self) -> None:
        self._settings.custom_backends = [
            {"display_name": b.display_name, "base_url": b.base_url}
            for b in self._registry.backends if isinstance(b, OpenAICompatibleBackend)
        ]
