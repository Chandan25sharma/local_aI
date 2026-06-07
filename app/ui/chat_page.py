"""The Chat page: session list, model/persona pickers, message thread, and input box."""
from __future__ import annotations

import getpass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from app.backends.base import ChatMessage
from app.backends.registry import BackendRegistry
from app.core.chat_session import ChatSession
from app.core.settings import PERSONA_PRESETS, AppSettings
from app.core.workers import BackendStatusWorker, ChatWorker
from app.ui.widgets.message_bubble import MessageBubble


class _ChatInput(QPlainTextEdit):
    """Message box where Enter sends and Shift+Enter inserts a newline (standard chat UX)."""

    send_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


_STARTER_PROMPTS = [
    ("Explain this code", "Can you explain what this code does, step by step?\n\n```\n# paste your code here\n```"),
    ("Find a bug", "I'm hitting an error / unexpected behavior. Here's the code and what happens:\n\n```\n# paste your code here\n```\n\nWhat I expected vs. what I got:\n"),
    ("Write a function", "Write a function that "),
    ("Review my code", "Please review this code for bugs, style, and possible improvements:\n\n```\n# paste your code here\n```"),
]


class ChatPage(QWidget):
    """The chat surface itself — top bar, message thread, and input box.

    The session list and New-chat control live in MainWindow's merged sidebar now
    (Claude-style single panel); this page just renders/streams the active session
    and tells the outside world when the saved-session set changes via `sessions_changed`.
    """

    sessions_changed = Signal()

    @property
    def current_session_id(self) -> str | None:
        return self._session.id if self._session else None

    def __init__(self, registry: BackendRegistry, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._settings = settings
        self._session: ChatSession | None = None
        self._chat_worker: ChatWorker | None = None
        self._status_worker: BackendStatusWorker | None = None
        self._pending_assistant_bubble: MessageBubble | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("chatScroll")
        self._thread_container = QWidget()
        self._thread_layout = QVBoxLayout(self._thread_container)
        self._thread_layout.setContentsMargins(16, 16, 16, 16)
        self._thread_layout.setSpacing(12)
        self._thread_layout.addStretch(1)
        self._scroll.setWidget(self._thread_container)

        # New chats open on a centered welcome screen (greeting + quick-start prompts);
        # once the first message lands, we switch to the scrolling thread view.
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._build_welcome_view())
        self._content_stack.addWidget(self._scroll)
        layout.addWidget(self._content_stack, 1)

        layout.addWidget(self._build_input_bar())

        self._populate_backend_selector()
        self.start_new_chat()

    def _build_welcome_view(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("welcomeView")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)
        layout.addStretch(2)

        # A fixed-width inner column keeps the greeting centered and prevents long
        # text from forcing the whole page (and the splitter) wider than the window.
        column = QWidget()
        column.setMaximumWidth(620)
        col_layout = QVBoxLayout(column)
        col_layout.setSpacing(14)

        name = getpass.getuser().split("\\")[-1].title()
        greeting = QLabel(f"What can I help with, {name}?")
        greeting.setObjectName("welcomeGreeting")
        greeting.setAlignment(Qt.AlignCenter)
        greeting.setWordWrap(True)
        col_layout.addWidget(greeting)

        subtitle = QLabel(
            "Ask a coding question, paste an error, or describe what you want to build. "
            "Your local model replies right here — completely offline."
        )
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        col_layout.addWidget(subtitle)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch(1)
        for label, prompt in _STARTER_PROMPTS:
            chip = QPushButton(label)
            chip.setObjectName("starterChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _checked=False, p=prompt: self._use_starter_prompt(p))
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        col_layout.addLayout(chips_row)

        layout.addWidget(column, 0, Qt.AlignHCenter)
        layout.addStretch(3)
        return wrap

    def _use_starter_prompt(self, prompt: str) -> None:
        self._input.setPlainText(prompt)
        self._input.setFocus()
        cursor = self._input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._input.setTextCursor(cursor)

    def _update_content_view(self) -> None:
        has_messages = bool(self._session and self._session.messages)
        self._content_stack.setCurrentIndex(1 if has_messages else 0)

    # ------------------------------------------------------------------
    # Session lifecycle — driven by MainWindow's merged sidebar
    # ------------------------------------------------------------------
    def start_new_chat(self) -> None:
        backend = self._current_backend()
        session = ChatSession(
            backend_name=backend.name if backend else "ollama",
            model=self._model_selector.currentText(),
            persona=self._persona_selector.currentText(),
        )
        self.load_session(session, persist_immediately=False)

    def load_session(self, session: ChatSession, persist_immediately: bool = True) -> None:
        self._cancel_active_stream()
        self._session = session
        self._clear_thread()
        for msg in session.messages:
            self._append_bubble(msg.role, msg.content)
        self._update_content_view()
        self._scroll_to_bottom()
        if persist_immediately:
            session.save()

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        # Compact pickers — no text labels (tooltips explain them instead), with capped
        # widths so the three of them plus the status pill always fit without overflowing.
        self._backend_selector = QComboBox()
        self._backend_selector.setObjectName("pickerCombo")
        self._backend_selector.setToolTip("Backend — which local LLM server to talk to")
        self._backend_selector.setMaximumWidth(150)
        self._backend_selector.currentIndexChanged.connect(self._on_backend_changed)
        layout.addWidget(self._backend_selector)

        self._model_selector = QComboBox()
        self._model_selector.setObjectName("pickerCombo")
        self._model_selector.setToolTip("Model — which installed model replies to you")
        self._model_selector.setMinimumWidth(150)
        self._model_selector.setMaximumWidth(220)
        layout.addWidget(self._model_selector)

        self._persona_selector = QComboBox()
        self._persona_selector.setObjectName("pickerCombo")
        self._persona_selector.setToolTip("Persona — the style/system prompt the assistant replies with")
        self._persona_selector.setMaximumWidth(160)
        self._persona_selector.addItems(list(PERSONA_PRESETS.keys()))
        self._persona_selector.setCurrentText(self._settings.persona)
        layout.addWidget(self._persona_selector)

        layout.addStretch(1)
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(self._status_label)
        return bar

    def _build_input_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("inputBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        self._input = _ChatInput()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Ask anything — coding help, explanations, reviews…  (Enter to send, Shift+Enter for a new line)")
        self._input.setFixedHeight(72)
        self._input.send_requested.connect(self._on_send_clicked)
        layout.addWidget(self._input, 1)

        button_col = QVBoxLayout()
        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("primaryBtn")
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setFixedWidth(90)
        self._send_btn.clicked.connect(self._on_send_clicked)
        button_col.addWidget(self._send_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setFixedWidth(90)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._cancel_active_stream)
        button_col.addWidget(self._stop_btn)
        layout.addLayout(button_col)
        return bar

    # ------------------------------------------------------------------
    # Backend / model selection
    # ------------------------------------------------------------------
    def _populate_backend_selector(self) -> None:
        self._backend_selector.blockSignals(True)
        self._backend_selector.clear()
        for backend in self._registry.backends:
            self._backend_selector.addItem(backend.display_name, backend.name)
        idx = self._backend_selector.findData(self._settings.last_backend)
        if idx >= 0:
            self._backend_selector.setCurrentIndex(idx)
        self._backend_selector.blockSignals(False)
        self._on_backend_changed()

    def refresh_backends(self) -> None:
        """Called by the main window when backends are added/removed in Settings."""
        current = self._backend_selector.currentData()
        self._populate_backend_selector()
        idx = self._backend_selector.findData(current)
        if idx >= 0:
            self._backend_selector.setCurrentIndex(idx)

    def _current_backend(self):
        name = self._backend_selector.currentData()
        return self._registry.get(name) if name else None

    def _on_backend_changed(self) -> None:
        backend = self._current_backend()
        self._model_selector.clear()
        if backend is None:
            return
        self._settings.last_backend = backend.name
        self._status_label.setText("Checking…")
        self._status_worker = BackendStatusWorker(backend)
        self._status_worker.result.connect(self._on_backend_status)
        self._status_worker.failed.connect(self._on_backend_status_failed)
        self._status_worker.start()

    def _on_backend_status(self, backend, available: bool, models: list) -> None:
        if backend is not self._current_backend():
            return
        if not available:
            self._status_label.setText(f"⚠ {backend.display_name} not reachable")
            return
        self._status_label.setText(f"✓ {backend.display_name} — {len(models)} model(s)")
        self._model_selector.clear()
        for m in models:
            self._model_selector.addItem(m.name)
        preferred = self._settings.last_model
        idx = self._model_selector.findText(preferred)
        if idx >= 0:
            self._model_selector.setCurrentIndex(idx)

    def _on_backend_status_failed(self, backend, message: str) -> None:
        if backend is self._current_backend():
            self._status_label.setText(f"⚠ {message}")

    # ------------------------------------------------------------------
    # Sending messages / streaming
    # ------------------------------------------------------------------
    def _on_send_clicked(self) -> None:
        text = self._input.toPlainText().strip()
        if not text or self._chat_worker is not None:
            return
        backend = self._current_backend()
        if backend is None:
            QMessageBox.warning(self, "No backend", "No backend is configured. Add one from Settings.")
            return
        model = self._model_selector.currentText().strip()
        if not model:
            QMessageBox.warning(self, "No model selected",
                                f"{backend.display_name} has no model selected. Pull or select one from the Models page.")
            return

        self._settings.last_model = model
        self._settings.persona = self._persona_selector.currentText()

        session = self._session
        if session is None:
            return
        session.backend_name = backend.name
        session.model = model
        session.persona = self._persona_selector.currentText()

        self._input.clear()
        user_msg = ChatMessage(role="user", content=text)
        session.messages.append(user_msg)
        self._update_content_view()
        self._append_bubble("user", text)

        persona_prompt = PERSONA_PRESETS.get(session.persona, "")
        history: list[ChatMessage] = []
        if persona_prompt:
            history.append(ChatMessage(role="system", content=persona_prompt))
        history.extend(session.messages)

        self._pending_assistant_bubble = self._append_bubble("assistant", "", streaming=True)
        self._set_streaming_state(True)

        self._chat_worker = ChatWorker(backend, model, history)
        self._chat_worker.token_received.connect(self._on_token)
        self._chat_worker.finished_ok.connect(self._on_stream_finished)
        self._chat_worker.failed.connect(self._on_stream_failed)
        self._chat_worker.start()

    def _on_token(self, token: str) -> None:
        if self._pending_assistant_bubble is not None:
            self._pending_assistant_bubble.append_token(token)
            self._scroll_to_bottom()

    def _on_stream_finished(self) -> None:
        bubble = self._pending_assistant_bubble
        session = self._session
        if bubble is not None:
            bubble.finalize()
            if session is not None:
                is_first_reply = len(session.messages) == 1
                session.messages.append(ChatMessage(role="assistant", content=bubble._raw_content))
                if is_first_reply:
                    session.derive_title_from_first_message()
                session.save()
                self.sessions_changed.emit()
        self._finish_stream()

    def _on_stream_failed(self, message: str) -> None:
        if self._pending_assistant_bubble is not None:
            self._pending_assistant_bubble.append_token(f"\n\n*⚠ Error: {message}*")
            self._pending_assistant_bubble.finalize()
        self._finish_stream()

    def _finish_stream(self) -> None:
        self._pending_assistant_bubble = None
        self._chat_worker = None
        self._set_streaming_state(False)
        self._scroll_to_bottom()

    def _cancel_active_stream(self) -> None:
        if self._chat_worker is not None:
            self._chat_worker.stop()
            self._chat_worker.token_received.disconnect(self._on_token)
            if self._pending_assistant_bubble is not None:
                self._pending_assistant_bubble.finalize()
            self._finish_stream()

    def _set_streaming_state(self, streaming: bool) -> None:
        self._send_btn.setVisible(not streaming)
        self._stop_btn.setVisible(streaming)
        self._input.setEnabled(not streaming)

    # ------------------------------------------------------------------
    # Thread rendering helpers
    # ------------------------------------------------------------------
    def _clear_thread(self) -> None:
        while self._thread_layout.count() > 1:
            item = self._thread_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _append_bubble(self, role: str, content: str, streaming: bool = False) -> MessageBubble:
        bubble = MessageBubble(role, content, streaming=streaming)
        self._thread_layout.insertWidget(self._thread_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))
