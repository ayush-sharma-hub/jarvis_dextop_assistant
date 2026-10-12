"""Typed environment configuration. Secrets are read only from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_or_none(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


SUPPORTED_PROVIDERS = {"ollama", "gemini", "openai", "free_web"}


@dataclass(frozen=True)
class Settings:
    wake_words: tuple[str, ...]
    microphone_index: int | None
    command_timeout_seconds: int
    phrase_time_limit_seconds: int
    action_mode: str
    pyautogui_pause_seconds: float
    gemini_api_key: str | None
    gemini_model: str
    openai_api_key: str | None
    openai_model: str
    ollama_url: str
    ollama_model: str
    provider_order: tuple[str, ...]
    llm_max_attempts: int
    llm_retry_seconds: float
    tts_rate: int
    tts_voice: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        words = tuple(
            word.strip().lower()
            for word in os.getenv("WAKE_WORDS", "jarvis,hey jarvis,friday").split(",")
            if word.strip()
        )
        mode = os.getenv("ACTION_MODE", "auto").strip().lower()
        if mode not in {"confirm", "auto", "disabled"}:
            raise ValueError("ACTION_MODE must be confirm, auto, or disabled")

        configured_gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        legacy_defaults = {"gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite"}
        gemini_model = "gemini-3.8-flash" if configured_gemini_model in legacy_defaults else configured_gemini_model

        provider_order = tuple(
            name.strip().lower()
            for name in os.getenv("BRAIN_PROVIDER_ORDER", "gemini,openai,free_web").split(",")
            if name.strip()
        )
        invalid_providers = set(provider_order) - SUPPORTED_PROVIDERS
        if invalid_providers:
            raise ValueError(f"Unsupported provider(s): {', '.join(sorted(invalid_providers))}")

        return cls(
            wake_words=words,
            microphone_index=_int_or_none("MICROPHONE_INDEX"),
            command_timeout_seconds=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "8")),
            phrase_time_limit_seconds=int(os.getenv("PHRASE_TIME_LIMIT_SECONDS", "12")),
            action_mode=mode,
            pyautogui_pause_seconds=float(os.getenv("PYAUTOGUI_PAUSE_SECONDS", "0.15")),
            gemini_api_key=(os.getenv("GEMINI_API_KEY") or "").strip() or None,
            gemini_model=gemini_model,
            openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            provider_order=provider_order,
            llm_max_attempts=max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "2"))),
            llm_retry_seconds=max(0.5, float(os.getenv("LLM_RETRY_SECONDS", "1.5"))),
            tts_rate=int(os.getenv("TTS_RATE", "185")),
            tts_voice=(os.getenv("TTS_VOICE") or "").strip() or None,
        )
