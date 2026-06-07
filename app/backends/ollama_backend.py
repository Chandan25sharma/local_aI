"""Backend for Ollama (https://ollama.com) — talks to its local REST API on localhost:11434."""
from __future__ import annotations

import json
from typing import Callable, Iterable

import requests

from .base import ChatMessage, LLMBackend, ModelInfo

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaBackend(LLMBackend):
    name = "ollama"
    display_name = "Ollama"

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.ok
        except requests.RequestException:
            return False

    def list_models(self) -> list[ModelInfo]:
        r = requests.get(f"{self.base_url}/api/tags", timeout=5)
        r.raise_for_status()
        models = []
        for m in r.json().get("models", []):
            models.append(ModelInfo(
                name=m.get("name") or m.get("model", ""),
                size_bytes=m.get("size", 0),
                modified_at=m.get("modified_at", ""),
            ))
        return models

    def chat_stream(
        self,
        model: str,
        messages: Iterable[ChatMessage],
        on_token: Callable[[str], None],
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if should_stop is not None and should_stop():
                    return
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                content = chunk.get("message", {}).get("content", "")
                if content:
                    on_token(content)
                if chunk.get("done"):
                    return

    def supports_model_management(self) -> bool:
        return True

    def pull_model(self, name: str, on_progress: Callable[[str, int, int], None]) -> None:
        payload = {"model": name, "stream": True}
        with requests.post(f"{self.base_url}/api/pull", json=payload, stream=True, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                status = chunk.get("status", "")
                total = chunk.get("total", 0)
                completed = chunk.get("completed", 0)
                on_progress(status, completed, total)
                if status == "success":
                    return

    def delete_model(self, name: str) -> None:
        r = requests.delete(f"{self.base_url}/api/delete", json={"model": name}, timeout=30)
        r.raise_for_status()
