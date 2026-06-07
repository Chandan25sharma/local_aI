"""Persists chat conversations as JSON files under the user's app-data directory."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from app.backends.base import ChatMessage


def sessions_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    path = Path(base) / "chats"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class ChatSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = "New chat"
    backend_name: str = "ollama"
    model: str = ""
    persona: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # ---- persistence -------------------------------------------------
    def _path(self) -> Path:
        return sessions_dir() / f"{self.id}.json"

    def save(self) -> None:
        data = {
            "id": self.id,
            "title": self.title,
            "backend_name": self.backend_name,
            "model": self.model,
            "persona": self.persona,
            "created_at": self.created_at,
            "messages": [m.to_dict() for m in self.messages],
        }
        self._path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def delete(self) -> None:
        path = self._path()
        if path.exists():
            path.unlink()

    @classmethod
    def load(cls, path: Path) -> "ChatSession":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            id=data.get("id", path.stem),
            title=data.get("title", "Chat"),
            backend_name=data.get("backend_name", "ollama"),
            model=data.get("model", ""),
            persona=data.get("persona", ""),
            messages=[ChatMessage(**m) for m in data.get("messages", [])],
            created_at=data.get("created_at", ""),
        )

    # ---- helpers ------------------------------------------------------
    def derive_title_from_first_message(self) -> None:
        for m in self.messages:
            if m.role == "user":
                text = re.sub(r"\s+", " ", m.content).strip()
                self.title = (text[:48] + "…") if len(text) > 48 else (text or "New chat")
                return


def list_sessions() -> list[ChatSession]:
    sessions = []
    for path in sorted(sessions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            sessions.append(ChatSession.load(path))
        except (json.JSONDecodeError, OSError, TypeError):
            continue
    return sessions
