"""Abstract interface that every local-LLM backend (Ollama, LM Studio, llama.cpp, ...) implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterable


class NotSupportedError(Exception):
    """Raised when a backend doesn't support an operation (e.g. model management on a generic OpenAI-compatible server)."""


@dataclass
class ModelInfo:
    name: str
    size_bytes: int = 0
    modified_at: str = ""

    @property
    def size_human(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


@dataclass
class ChatMessage:
    role: str   # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class LLMBackend(ABC):
    """Common contract the UI talks to, regardless of which local-LLM server is behind it."""

    name: str = "backend"
    display_name: str = "Backend"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend's server is reachable right now."""

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Return the models currently installed/available on this backend."""

    @abstractmethod
    def chat_stream(
        self,
        model: str,
        messages: Iterable[ChatMessage],
        on_token: Callable[[str], None],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        """Stream a chat completion, calling on_token(text_chunk) as tokens arrive.

        Blocks until the stream finishes, an error occurs, or should_stop() returns True.
        Intended to be called from a background worker thread, not the UI thread.
        """

    def supports_model_management(self) -> bool:
        return False

    def pull_model(self, name: str, on_progress: Callable[[str, int, int], None]) -> None:
        """Download/install a model. on_progress(status_text, completed_bytes, total_bytes)."""
        raise NotSupportedError(f"{self.display_name} does not support installing models from this app")

    def delete_model(self, name: str) -> None:
        raise NotSupportedError(f"{self.display_name} does not support deleting models from this app")
