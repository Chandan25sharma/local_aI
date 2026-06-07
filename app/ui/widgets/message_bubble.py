"""Renders one chat message: prose as markdown→HTML, fenced code blocks as
syntax-highlighted, individually-copyable panels — the payoff for a coding assistant.

While a reply is streaming in, tokens are appended to a cheap plain-text preview
(re-parsing markdown on every token would be slow and flickery for long code).
Once the stream finishes, `finalize()` swaps in the fully segmented, highlighted view.
"""
from __future__ import annotations

import re

import markdown as md
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

_THINKING_FRAMES = ["Thinking", "Thinking.", "Thinking..", "Thinking..."]

_CODE_FENCE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
_FORMATTER = HtmlFormatter(noclasses=True, style="monokai", nowrap=False)
_PYGMENTS_BG = "#272822"


def _highlight_code(code: str, language: str) -> str:
    try:
        lexer = get_lexer_by_name(language) if language else guess_lexer(code)
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")
    return highlight(code, lexer, _FORMATTER)


def _flash_copied(button: QPushButton) -> None:
    button.setText("Copied!")
    QTimer.singleShot(1200, lambda: button.setText("Copy"))


class _CodeBlock(QFrame):
    def __init__(self, code: str, language: str, parent=None):
        super().__init__(parent)
        self._code = code
        self.setObjectName("codeBlock")
        self.setStyleSheet(f"#codeBlock {{ background-color: {_PYGMENTS_BG}; border-radius: 6px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color: #1e1f1c; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 4, 6, 4)
        lang_label = QLabel(language or "code")
        lang_label.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("copyCodeBtn")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setFixedHeight(22)
        copy_btn.clicked.connect(self._copy)
        h_layout.addWidget(lang_label)
        h_layout.addStretch(1)
        h_layout.addWidget(copy_btn)
        self._copy_btn = copy_btn

        body = QTextEdit()
        body.setReadOnly(True)
        body.setHtml(_highlight_code(code, language))
        body.setStyleSheet(f"QTextEdit {{ background-color: {_PYGMENTS_BG}; border: none; padding: 8px; }}")
        body.setLineWrapMode(QTextEdit.NoWrap)
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        body.setFixedHeight(min(max(int(body.document().size().height()) + 20, 40), 420))

        layout.addWidget(header)
        layout.addWidget(body)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._code)
        _flash_copied(self._copy_btn)


class _ProseLabel(QLabel):
    def __init__(self, text: str, parent=None):
        html = md.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
        super().__init__(html, parent)
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.setOpenExternalLinks(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


class _PlainPreview(QLabel):
    """Lightweight raw-text view shown while a reply is still streaming in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setObjectName("streamingPreview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


class MessageBubble(QFrame):
    """A single chat message — role label, copy-all button, and rendered content."""

    def __init__(self, role: str, content: str = "", streaming: bool = False, parent=None):
        super().__init__(parent)
        self.role = role
        self._raw_content = ""
        self._streaming = streaming
        self.setObjectName("userBubble" if role == "user" else "assistantBubble")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        header = QHBoxLayout()
        role_label = QLabel("You" if role == "user" else "Assistant")
        role_label.setObjectName("roleLabel")
        header.addWidget(role_label)
        header.addStretch(1)
        self._copy_all_btn = QPushButton("Copy")
        self._copy_all_btn.setObjectName("copyAllBtn")
        self._copy_all_btn.setCursor(Qt.PointingHandCursor)
        self._copy_all_btn.setFixedHeight(22)
        self._copy_all_btn.clicked.connect(self._copy_all)
        header.addWidget(self._copy_all_btn)
        outer.addLayout(header)

        self._body_layout = QVBoxLayout()
        self._body_layout.setSpacing(8)
        outer.addLayout(self._body_layout)

        self._segment_widgets: list[QWidget] = []
        self._preview: _PlainPreview | None = None
        self._thinking_timer: QTimer | None = None
        self._thinking_frame = 0

        if streaming:
            self._preview = _PlainPreview()
            self._add_segment(self._preview)
            self._start_thinking_animation()
        elif content:
            self.set_content(content)
        self._raw_content = content

    # ---- "thinking…" placeholder, shown the instant a reply starts streaming ----
    def _start_thinking_animation(self) -> None:
        if self._preview is None:
            return
        self._preview.setObjectName("thinkingPreview")
        self._tick_thinking()
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(450)
        self._thinking_timer.timeout.connect(self._tick_thinking)
        self._thinking_timer.start()

    def _tick_thinking(self) -> None:
        if self._preview is None:
            return
        self._preview.setText(_THINKING_FRAMES[self._thinking_frame % len(_THINKING_FRAMES)])
        self._thinking_frame += 1

    def _stop_thinking_animation(self) -> None:
        if self._thinking_timer is None:
            return
        self._thinking_timer.stop()
        self._thinking_timer.deleteLater()
        self._thinking_timer = None
        if self._preview is not None:
            self._preview.setObjectName("streamingPreview")
            self._preview.setText("")
            self._preview.style().unpolish(self._preview)
            self._preview.style().polish(self._preview)

    # ---- streaming path ----------------------------------------------
    def append_token(self, token: str) -> None:
        if self._thinking_timer is not None:
            self._stop_thinking_animation()
        self._raw_content += token
        if self._preview is not None:
            self._preview.setText(self._raw_content)

    def finalize(self) -> None:
        """Stream finished — swap the plain preview for the fully rendered, highlighted view."""
        self._stop_thinking_animation()
        self._streaming = False
        self.set_content(self._raw_content)

    # ---- full render path ---------------------------------------------
    def _clear_segments(self) -> None:
        for w in self._segment_widgets:
            self._body_layout.removeWidget(w)
            w.deleteLater()
        self._segment_widgets.clear()
        self._preview = None

    def set_content(self, content: str) -> None:
        self._raw_content = content
        self._clear_segments()

        last_end = 0
        for match in _CODE_FENCE_RE.finditer(content):
            prose = content[last_end:match.start()]
            if prose.strip():
                self._add_segment(_ProseLabel(prose))
            language, code = match.group(1).strip(), match.group(2)
            self._add_segment(_CodeBlock(code.rstrip("\n"), language))
            last_end = match.end()

        tail = content[last_end:]
        if tail.strip() or not self._segment_widgets:
            self._add_segment(_ProseLabel(tail))

    def _add_segment(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)
        self._segment_widgets.append(widget)

    def _copy_all(self) -> None:
        QApplication.clipboard().setText(self._raw_content)
        _flash_copied(self._copy_all_btn)
