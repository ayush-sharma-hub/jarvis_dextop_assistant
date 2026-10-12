"""Multimodal reasoning providers, strict JSON parsing, and provider failover."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import Settings
from .vision import VisualContext


SYSTEM_PROMPT = """
You are J.A.R.V.I.S., Ayush's personal local AI desktop assistant (RIT Roorkee).
You are smart, helpful, witty, and speak naturally in Hinglish/English mix.
Call the user "bhai" or "yaar" - do NOT use "sir".

CRITICAL RULE - LOCAL ANSWERS ONLY (NO UNNECESSARY BROWSER):
Answer questions, explain concepts, provide ideas, advice, facts, code, and chat DIRECTLY using your own intelligence with action "none".
NEVER use action "search_web" unless the user EXPLICITLY asks to "search on google" or "google this".
Do NOT open browser tabs or Chrome for regular questions. Always speak the answer aloud in speech.

Return EXACTLY one JSON object and no Markdown, explanations, code fences, or extra keys:
{
  "action": "none|open_app|open_named_app|open_url|open_url_in_chrome|play_youtube|play_youtube_in_chrome|volume_up|volume_down|mute|media_play_pause|media_next|media_prev|search_web|move|click|double_click|type|press|hotkey|scroll|college_wifi_login|remember_fact|open_whatsapp",
  "speech": "what you will say aloud to the user in concise Hinglish / English",
  "app": "name of application to open" optional,
  "text": "query or url or text" optional,
  "x": integer optional, "y": integer optional,
  "key": string optional,
  "keys": [string] optional,
  "clicks": integer optional,
  "scrolls": integer optional
}

Rules:
- For ALL questions, knowledge queries, advice, jokes, conversations: use action "none" and answer directly in speech (1-3 sentences max).
- Only use action "play_youtube" when user asks to play a song/video.
- Only use action "open_named_app" when user asks to open an installed application.
- Only use action "open_whatsapp" when user asks to open WhatsApp.
- Only use action "college_wifi_login" when user asks to login to college WiFi.
- Only use action "search_web" if user explicitly demands to search Google in a browser.
- Do not perform destructive shell commands, formatting, deletion, or purchases.
""".strip()

ALLOWED_ACTIONS = {
    "none",
    "move",
    "click",
    "double_click",
    "type",
    "press",
    "hotkey",
    "scroll",
    "open_app",
    "open_named_app",
    "open_url",
    "open_url_in_chrome",
    "play_youtube",
    "play_youtube_in_chrome",
    "volume_up",
    "volume_down",
    "mute",
    "media_play_pause",
    "media_next",
    "media_prev",
    "search_web",
    "college_wifi_login",
    "remember_fact",
    "open_whatsapp",
}


class BrainError(RuntimeError):
    """Raised when every configured provider fails or returns malformed data."""


@dataclass(frozen=True)
class Decision:
    action: str
    speech: str
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None
    keys: tuple[str, ...] = ()
    clicks: int = 1
    scrolls: int = 0
    app: str | None = None

    @classmethod
    def from_json(cls, raw: str) -> "Decision":
        """Parse a model response defensively; rejection is safer than guessing."""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Attempt to extract embedded JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            data = None
            if match:
                try:
                    data = json.loads(match.group(0))
                    # The outer response was malformed, so this recovery must
                    # not authorize an action even if its embedded object does.
                    if isinstance(data, dict):
                        data = {**data, "action": "none"}
                except json.JSONDecodeError:
                    data = None

            if data is None:
                # Recovery is deliberately speech-only.  A malformed response must
                # never be able to request a desktop action.
                speech_match = re.search(r'"speech"\s*:\s*"(.*?)(?:"|\Z)', cleaned, re.DOTALL)
                if speech_match:
                    recovered_speech = speech_match.group(1).strip()
                    data = {"action": "none", "speech": recovered_speech}
                else:
                    raise BrainError("Provider did not return valid JSON") from exc

        if not isinstance(data, dict):
            raise BrainError("Provider response must be a JSON object")

        unknown = set(data) - {"action", "speech", "x", "y", "text", "key", "keys", "clicks", "scrolls", "app"}
        if unknown:
            raise BrainError(f"Provider used forbidden field(s): {', '.join(sorted(unknown))}")

        action = data.get("action", "none")
        speech = data.get("speech")
        if action not in ALLOWED_ACTIONS or not isinstance(speech, str) or not speech.strip():
            raise BrainError(f"Provider response has invalid action ({action}) or speech")

        for coordinate in ("x", "y"):
            if coordinate in data and (isinstance(data[coordinate], bool) or not isinstance(data[coordinate], int)):
                raise BrainError(f"{coordinate} must be an integer")
        if action in {"move", "click", "double_click"} and ("x" not in data or "y" not in data):
            raise BrainError(f"{action} requires x and y")
        if action == "type" and not isinstance(data.get("text"), str):
            raise BrainError("type requires text")
        if action == "press" and not isinstance(data.get("key"), str):
            raise BrainError("press requires key")

        raw_keys = data.get("keys", [])
        if action == "hotkey" and (not isinstance(raw_keys, list) or not all(isinstance(k, str) for k in raw_keys)):
            raise BrainError("hotkey requires a keys string array")

        for field in ("clicks", "scrolls"):
            if field in data and (isinstance(data[field], bool) or not isinstance(data[field], int)):
                raise BrainError(f"{field} must be an integer")
        if "app" in data and not isinstance(data["app"], str):
            raise BrainError("app must be a string")

        return cls(
            action=action,
            speech=speech.strip(),
            x=data.get("x"),
            y=data.get("y"),
            text=data.get("text"),
            key=data.get("key"),
            keys=tuple(raw_keys),
            clicks=data.get("clicks", 1),
            scrolls=data.get("scrolls", 0),
            app=data.get("app"),
        )


class Provider(Protocol):
    name: str

    def complete(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> str: ...


class GeminiBrain:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.fallback_models = [model, "gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    def complete(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> str:
        from google.genai import types

        mem_prefix = f"Context about the user and past conversation:\n{memory_context}\n\n" if memory_context else ""
        if context is None:
            prompt = f"{mem_prefix}Voice command: {command}\nNo visual context was requested. Return the required JSON now."
            parts: list[Any] = [prompt]
        else:
            prompt = (
                f"{mem_prefix}Voice command: {command}\n"
                f"The first image is the desktop screenshot ({context.screen_size[0]}x{context.screen_size[1]} pixels). "
                "The optional second image is the webcam frame. Return the required JSON now."
            )
            parts = [
                prompt,
                types.Part.from_bytes(data=context.screen_jpeg, mime_type="image/jpeg"),
            ]

        last_error = None
        for candidate_model in self.fallback_models:
            try:
                response = self.client.models.generate_content(
                    model=candidate_model,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.2,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                if response.text:
                    return response.text
            except Exception as exc:
                last_error = exc
                continue
        raise BrainError(f"Gemini generation failed on all models: {last_error}")


class OpenAIBrain:
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> str:
        mem_prefix = f"Context about user:\n{memory_context}\n\n" if memory_context else ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{mem_prefix}Voice command: {command}\nReturn the required JSON now."},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=12) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return content
        except Exception as exc:
            raise BrainError(f"OpenAI error: {exc}") from exc


class OllamaBrain:
    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        try:
            with urlopen(f"{self.base_url}/api/tags", timeout=0.5) as response:
                return 200 <= response.status < 300
        except (URLError, TimeoutError):
            return False

    def complete(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> str:
        mem_prefix = f"Context about the user and past conversation:\n{memory_context}\n\n" if memory_context else ""
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            # Qwen3's visible thinking mode is excellent for long reasoning but far
            # too slow and verbose for a desktop voice assistant.
            "think": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{mem_prefix}Voice command: {command}\nReturn the required JSON now."},
            ],
            "options": {
                "temperature": 0.3,
                "num_predict": 160,
                "num_ctx": 1024,
            },
            "keep_alive": "24h",
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # First local request may need time to load a multi-GB model into RAM/VRAM.
        # Subsequent requests stay warm for 24 hours via keep_alive above.
        with urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body.get("message", {}).get("content")
        if not isinstance(content, str):
            raise BrainError("Ollama returned no message content")
        return content


class FreeWebBrain:
    """Free web knowledge provider querying Wikipedia and DuckDuckGo."""

    name = "free_web"

    def complete(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> str:
        clean = re.sub(r"^(?:who is|who was|what is|what was|tell me about|explain|search for)\s+", "", command, flags=re.IGNORECASE).strip(" ?.")
        if not clean:
            clean = command

        # Try Wikipedia Summary API
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean)}"
            req = Request(url, headers={"User-Agent": "JarvisDesktopAssistant/1.0"})
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                extract = data.get("extract")
                if extract:
                    # Take first 2 sentences for concise speech
                    sentences = extract.split(". ")
                    concise = ". ".join(sentences[:2]).rstrip(".") + "."
                    speech = f"{concise}"
                    return json.dumps({"action": "none", "speech": speech})
        except Exception as exc:
            logging.getLogger(self.__class__.__name__).debug("Wikipedia lookup failed: %s", exc)

        # Try DuckDuckGo Instant Answer API
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(clean)}&format=json&no_html=1&skip_disambig=1"
            req = Request(ddg_url, headers={"User-Agent": "JarvisDesktopAssistant/1.0"})
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                answer = data.get("AbstractText") or data.get("Answer")
                if answer:
                    sentences = answer.split(". ")
                    concise = ". ".join(sentences[:2]).rstrip(".") + "."
                    return json.dumps({"action": "none", "speech": f"{concise}"})
        except Exception as exc:
            logging.getLogger(self.__class__.__name__).debug("DuckDuckGo lookup failed: %s", exc)

        # Only open Chrome if user explicitly demanded web search
        if any(term in command.lower() for term in ["google", "search", "browse", "net pe"]):
            return json.dumps({
                "action": "search_web",
                "text": clean,
                "speech": f"Google pe search kar raha hun bhai: {clean}",
            })

        return json.dumps({
            "action": "none",
            "speech": f"Bhai, {clean} ke baare mein main samajh gaya. Batao ispe kya detail chahiye?",
        })


class FailoverBrain:
    """Orchestrates providers in configured order with graceful fallbacks."""

    def __init__(self, settings: Settings) -> None:
        self.log = logging.getLogger(self.__class__.__name__)
        self.max_attempts = settings.llm_max_attempts
        self.retry_seconds = settings.llm_retry_seconds
        self.providers: list[Provider] = []

        for provider_name in settings.provider_order:
            if provider_name == "gemini" and settings.gemini_api_key:
                try:
                    self.providers.append(GeminiBrain(settings.gemini_api_key, settings.gemini_model))
                    self.log.info("Gemini provider enabled (%s).", settings.gemini_model)
                except Exception as exc:
                    self.log.warning("Could not initialize Gemini: %s", exc)
            elif provider_name == "openai" and settings.openai_api_key:
                try:
                    self.providers.append(OpenAIBrain(settings.openai_api_key, settings.openai_model))
                    self.log.info("OpenAI provider enabled (%s).", settings.openai_model)
                except Exception as exc:
                    self.log.warning("Could not initialize OpenAI: %s", exc)
            elif provider_name == "ollama":
                ollama = OllamaBrain(settings.ollama_url, settings.ollama_model)
                if ollama.is_available():
                    self.providers.append(ollama)
                    self.log.info("Ollama provider enabled (%s).", settings.ollama_model)
            elif provider_name == "free_web":
                self.providers.append(FreeWebBrain())
                self.log.info("Free Web Knowledge provider enabled.")

    @property
    def available_providers(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self.providers)

    def decide(self, command: str, context: VisualContext | None = None, memory_context: str = "") -> Decision:
        errors: list[str] = []
        for provider in self.providers:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    raw = provider.complete(command, context, memory_context=memory_context)
                    return Decision.from_json(raw)
                except Exception as exc:
                    is_last = attempt == self.max_attempts
                    if not is_last and self._is_transient(exc):
                        time.sleep(self.retry_seconds)
                        continue
                    self.log.warning("Provider %s failed: %s", provider.name, exc)
                    errors.append(f"{provider.name}: {exc}")
                    break
        raise BrainError("; ".join(errors) or "no available providers")

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        msg = str(exc).upper()
        return any(m in msg for m in ("429", "500", "502", "503", "504", "UNAVAILABLE", "TIMEOUT"))
