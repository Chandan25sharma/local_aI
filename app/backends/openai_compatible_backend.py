"""Generic backend for any local server exposing an OpenAI-compatible REST API
(LM Studio, llama.cpp `server`, vLLM, text-generation-webui, ...).

These tools don't share a standard model-management API, so this backend only
implements chat + listing — installing/removing models stays in each tool's own UI.
"""
from __future__ import annotations

import json
from typing import Callable, Iterable

import requests

from .base import ChatMessage, LLMBackend, ModelInfo


class OpenAICompatibleBackend(LLMBackend):
    name = "openai_compatible"

    def __init__(self, display_name: str, base_url: str):
        self.display_name = display_name
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/models", timeout=2)
            return r.ok
        except requests.RequestException:
            return False

    def list_models(self) -> list[ModelInfo]:
        r = requests.get(f"{self.base_url}/models", timeout=5)
        r.raise_for_status()
        models = []
        for m in r.json().get("data", []):
            models.append(ModelInfo(name=m.get("id", "")))
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
        with requests.post(f"{self.base_url}/chat/completions", json=payload, stream=True, timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if should_stop is not None and should_stop():
                    return
                if not line:
                    continue
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if not text.startswith("data:"):
                    continue
                data = text[len("data:"):].strip()
                if data == "[DONE]":
                    return
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    on_token(content)
                if choices[0].get("finish_reason"):
                    return
