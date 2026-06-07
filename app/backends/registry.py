"""Keeps track of configured backends and which one + model is currently active for chat."""
from __future__ import annotations

from .base import LLMBackend
from .ollama_backend import OllamaBackend
from .openai_compatible_backend import OpenAICompatibleBackend

# (display_name, base_url) presets users can pick from when adding an OpenAI-compatible backend
OPENAI_COMPATIBLE_PRESETS = [
    ("LM Studio", "http://localhost:1234/v1"),
    ("llama.cpp server", "http://localhost:8080/v1"),
    ("vLLM", "http://localhost:8000/v1"),
]


class BackendRegistry:
    def __init__(self):
        self._backends: list[LLMBackend] = [OllamaBackend()]

    @property
    def backends(self) -> list[LLMBackend]:
        return list(self._backends)

    def get(self, name: str) -> LLMBackend | None:
        return next((b for b in self._backends if b.name == name), None)

    def add_openai_compatible(self, display_name: str, base_url: str) -> LLMBackend:
        backend = OpenAICompatibleBackend(display_name, base_url)
        # Replace any existing custom backend with the same display name instead of duplicating
        self._backends = [b for b in self._backends if not (b.name == "openai_compatible" and b.display_name == display_name)]
        self._backends.append(backend)
        return backend

    def remove(self, backend: LLMBackend) -> None:
        if isinstance(backend, OllamaBackend):
            return  # Ollama is always available as the default backend
        self._backends = [b for b in self._backends if b is not backend]
