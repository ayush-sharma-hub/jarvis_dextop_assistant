"""
Jarvis Conversation Memory — tracks session turns and persistent facts (user name, preferences).
Persists to jarvis_memory.json.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MEMORY_FILE = Path(__file__).parent.parent / "jarvis_memory.json"
MAX_SESSION_TURNS = 20
MAX_PERSIST_FACTS = 50


class ConversationMemory:
    """Short-term session memory + long-term persistent fact storage."""

    def __init__(self) -> None:
        self._turns: deque[dict] = deque(maxlen=MAX_SESSION_TURNS)
        self._facts: list[str] = []
        self._user_name: str = "Ayush"
        self._session_start = datetime.now()
        self._load_persistent()

    def _load_persistent(self) -> None:
        try:
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                self._facts = data.get("facts", [])[-MAX_PERSIST_FACTS:]
                self._user_name = data.get("user_name", "Ayush")
                log.info("Memory loaded: user=%s, facts=%d", self._user_name, len(self._facts))
            else:
                self._facts = [
                    "User's name is Ayush",
                    "Student at RIT Roorkee (Roorkee Institute of Technology)",
                    "Compiling and presenting at Manthan AI Hackathon",
                ]
                self.save_persistent()
        except Exception as exc:
            log.warning("Memory load failed: %s", exc)

    def save_persistent(self) -> None:
        try:
            data = {
                "user_name": self._user_name,
                "facts": self._facts,
                "updated": datetime.now().isoformat(),
            }
            MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Memory save failed: %s", exc)

    @property
    def user_name(self) -> str:
        return self._user_name

    def set_user_name(self, name: str) -> None:
        if name:
            clean_name = name.strip().title()
            self._user_name = clean_name
            self.remember_fact(f"User's name is {clean_name}")
            self.save_persistent()

    def remember_fact(self, fact: str) -> None:
        if fact and fact not in self._facts:
            self._facts.append(fact)
            if len(self._facts) > MAX_PERSIST_FACTS:
                self._facts.pop(0)
            self.save_persistent()

    def add_turn(self, user: str, assistant: str) -> None:
        self._turns.append({
            "time": datetime.now().strftime("%H:%M"),
            "user": user,
            "assistant": assistant,
        })

    @property
    def recent_turns(self) -> list[dict]:
        return list(self._turns)

    def build_context_block(self) -> str:
        lines: list[str] = [
            f"User's Name: {self._user_name}",
            "College: Roorkee Institute of Technology (RIT Roorkee)",
        ]
        if self._facts:
            lines.append("== Known Facts ==")
            for f in self._facts[-10:]:
                lines.append(f"  - {f}")

        if self._turns:
            lines.append("== Recent Conversation ==")
            for t in list(self._turns)[-5:]:
                lines.append(f"  User: {t['user']}")
                lines.append(f"  JARVIS: {t['assistant'][:120]}")

        return "\n".join(lines)

    @property
    def session_summary(self) -> str:
        dur = datetime.now() - self._session_start
        mins = int(dur.total_seconds() / 60)
        return f"{len(self._turns)} turns | {mins}m session | User: {self._user_name}"