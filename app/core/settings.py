"""Thin wrapper around QSettings for the app's small set of persisted preferences."""
from __future__ import annotations

from PySide6.QtCore import QSettings

ORG_NAME = "LocalAI"
APP_NAME = "LocalAI Assistant"

PERSONA_PRESETS = {
    "Coding helper": (
        "You are an expert programming assistant. Give clear, correct, well-explained "
        "answers with idiomatic code examples. Point out edge cases and pitfalls."
    ),
    "Explain simply": (
        "You are a patient teacher explaining concepts to a beginner. Use plain language, "
        "short sentences, and concrete everyday analogies. Avoid jargon, or define it when used."
    ),
    "Code reviewer": (
        "You are a meticulous senior code reviewer. Critique the given code for correctness, "
        "readability, performance, and security. Suggest concrete improvements with reasoning."
    ),
    "Plain assistant": "You are a helpful, concise assistant.",
}
DEFAULT_PERSONA = "Coding helper"


class AppSettings:
    def __init__(self):
        self._qs = QSettings(ORG_NAME, APP_NAME)

    @property
    def theme(self) -> str:
        return self._qs.value("theme", "dark")

    @theme.setter
    def theme(self, value: str) -> None:
        self._qs.setValue("theme", value)

    @property
    def last_backend(self) -> str:
        return self._qs.value("last_backend", "ollama")

    @last_backend.setter
    def last_backend(self, value: str) -> None:
        self._qs.setValue("last_backend", value)

    @property
    def last_model(self) -> str:
        return self._qs.value("last_model", "")

    @last_model.setter
    def last_model(self, value: str) -> None:
        self._qs.setValue("last_model", value)

    @property
    def persona(self) -> str:
        return self._qs.value("persona", DEFAULT_PERSONA)

    @persona.setter
    def persona(self, value: str) -> None:
        self._qs.setValue("persona", value)

    @property
    def custom_backends(self) -> list[dict]:
        """List of {"display_name": ..., "base_url": ...} dicts for user-added OpenAI-compatible servers."""
        raw = self._qs.value("custom_backends", [])
        return raw if isinstance(raw, list) else []

    @custom_backends.setter
    def custom_backends(self, value: list[dict]) -> None:
        self._qs.setValue("custom_backends", value)
