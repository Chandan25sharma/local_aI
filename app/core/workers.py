"""QThread-based workers that run backend network I/O off the UI thread.

Each worker emits Qt signals back to the UI thread (token/progress/result/error/finished),
which is the standard PySide6 pattern for keeping the interface responsive during
long-running streaming chat replies and multi-gigabyte model downloads.
"""
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QThread, Signal

from app.backends.base import ChatMessage, LLMBackend, ModelInfo


class ChatWorker(QThread):
    token_received = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, backend: LLMBackend, model: str, messages: list[ChatMessage], parent=None):
        super().__init__(parent)
        self._backend = backend
        self._model = model
        self._messages = messages
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            self._backend.chat_stream(
                self._model,
                self._messages,
                on_token=self.token_received.emit,
                should_stop=lambda: self._stop_requested,
            )
            if not self._stop_requested:
                self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001 — surface any backend error to the UI
            if not self._stop_requested:
                self.failed.emit(str(exc))


class PullWorker(QThread):
    progress = Signal(str, int, int)  # status, completed_bytes, total_bytes
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, backend: LLMBackend, model_name: str, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._model_name = model_name

    def run(self) -> None:
        try:
            self._backend.pull_model(self._model_name, on_progress=self.progress.emit)
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class BackendStatusWorker(QThread):
    """Checks availability and (if available) lists models for one backend."""
    result = Signal(object, bool, list)  # backend, is_available, list[ModelInfo]
    failed = Signal(object, str)

    def __init__(self, backend: LLMBackend, parent=None):
        super().__init__(parent)
        self._backend = backend

    def run(self) -> None:
        try:
            available = self._backend.is_available()
            models: list[ModelInfo] = self._backend.list_models() if available else []
            self.result.emit(self._backend, available, models)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self._backend, str(exc))


class DeleteModelWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str, str)

    def __init__(self, backend: LLMBackend, model_name: str, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._model_name = model_name

    def run(self) -> None:
        try:
            self._backend.delete_model(self._model_name)
            self.finished_ok.emit(self._model_name)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self._model_name, str(exc))
