"""Text-to-speech module — dynamic neural voice via edge-tts with SAPI fallback."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import subprocess
import threading
from typing import Optional


log = logging.getLogger(__name__)

# ── Available edge-tts voices (free, neural, no GPU needed) ─────────────────
# All are Microsoft neural voices streamed from the Edge TTS service.
EDGE_VOICE_MAP: dict[str, str] = {
    # Indian / Hindi voices (Top recommendation for Hinglish & Indian English)
    "madhur":  "hi-IN-MadhurNeural",             # Young Indian male, fluent Hinglish
    "swara":   "hi-IN-SwaraNeural",              # Indian female, fluent Hindi
    "prabhat": "en-IN-PrabhatNeural",            # Indian English male
    "neerja":  "en-IN-NeerjaNeural",             # Indian English female
    "indian":  "hi-IN-MadhurNeural",
    "hindi":   "hi-IN-MadhurNeural",
    # English male voices
    "ryan":    "en-GB-RyanNeural",               # British, formal
    "guy":     "en-US-GuyNeural",                # American, confident
    "eric":    "en-US-EricNeural",               # American, calm
    "brian":   "en-US-BrianMultilingualNeural",  # Modern American
    # English female voices
    "aria":    "en-US-AriaNeural",
    "jenny":   "en-US-JennyNeural",
}

DEFAULT_VOICE = "hi-IN-MadhurNeural"  # Natural Indian voice for Hinglish / Gen-Z JARVIS

def _clean_for_speech(text: str) -> str:
    """Strip markdown, URLs, and code fences so speech sounds natural."""
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"`.*?`", "", cleaned)
    cleaned = re.sub(r"[*_#~|]", "", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def _edge_speak_async(text: str, voice: str, rate: str = "+0%", volume: str = "+0%") -> bool:
    """Stream and play audio using edge-tts. Returns True on success."""
    try:
        import edge_tts
        import sounddevice as sd
        import soundfile as sf

        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)

        # Stream audio bytes into a buffer
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)
        if audio_buffer.getbuffer().nbytes < 100:
            return False

        # Decode MP3 → numpy array → play via sounddevice
        data, samplerate = sf.read(audio_buffer, dtype="float32")
        sd.play(data, samplerate=samplerate)
        sd.wait()
        return True

    except Exception as exc:
        log.warning("edge-tts playback failed: %s", exc)
        return False


def _edge_speak_sync(text: str, voice: str, rate_pct: int = 0) -> bool:
    """Run the async edge_speak in a fresh event loop. Returns True on success."""
    try:
        rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_edge_speak_async(text, voice, rate=rate_str))
        finally:
            loop.close()
    except Exception as exc:
        log.warning("edge-tts sync wrapper failed: %s", exc)
        return False


class SpeechModule:
    """Dynamic neural text-to-speech.

    Tier 1: edge-tts  — Microsoft neural voice (sounds like a real person, free, CPU-only)
    Tier 2: Windows SAPI COM — the classic robot voice fallback
    Tier 3: PowerShell SAPI — if COM fails
    Tier 4: pyttsx3 — last resort
    """

    def __init__(self, rate: int = 185, voice_name: Optional[str] = None) -> None:
        self.log = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()

        # Map TTS_RATE (150-220 scale) → edge-tts % adjustment
        if rate > 10:
            self._edge_rate_pct = int((rate - 170) / 4)  # 170 = 0%, 185 ≈ +4%
        else:
            self._edge_rate_pct = rate

        # Map TTS_RATE to SAPI rate (-10 to 10)
        if rate > 10:
            sapi_rate = max(-10, min(10, int((rate - 150) / 25)))
            self._sapi_rate = max(1, sapi_rate)
        else:
            self._sapi_rate = rate

        # Resolve voice name → edge-tts voice identifier
        requested = (voice_name or "ryan").lower().strip()
        self.edge_voice = EDGE_VOICE_MAP.get(requested, DEFAULT_VOICE)
        self._sapi_voice_hint = requested  # used for SAPI fallback

        self.log.info(
            "SpeechModule: edge-tts voice=%s  rate=%+d%%  sapi_rate=%d",
            self.edge_voice, self._edge_rate_pct, self._sapi_rate,
        )

    def speak(self, text: str) -> None:
        """Speak aloud — tries neural voice first, falls back gracefully."""
        if not text:
            return
        clean_text = _clean_for_speech(text)
        if not clean_text:
            return

        self.log.info("JARVIS Speaking: %s", clean_text)
        print(f"\n[JARVIS]: {clean_text}\n")

        with self._lock:
            # ── Tier 1: edge-tts neural voice ──────────────────────────────
            if _edge_speak_sync(clean_text, self.edge_voice, self._edge_rate_pct):
                return

            # ── Tier 2: Windows COM SAPI.SpVoice ───────────────────────────
            try:
                import pythoncom
                import win32com.client

                pythoncom.CoInitialize()
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Rate = self._sapi_rate

                voices = voice.GetVoices()
                for i in range(voices.Count):
                    v = voices.Item(i)
                    desc = v.GetDescription().lower()
                    if self._sapi_voice_hint in desc:
                        voice.Voice = v
                        break

                voice.Speak(clean_text, 0)
                return
            except Exception as exc:
                self.log.warning("SAPI COM speak failed: %s. Trying PowerShell…", exc)

            # ── Tier 3: PowerShell SAPI ─────────────────────────────────────
            try:
                safe_text = clean_text.replace("'", "''")
                cmd = [
                    "powershell.exe", "-NoProfile", "-Command",
                    f"(New-Object -ComObject SAPI.SpVoice).Speak('{safe_text}')",
                ]
                subprocess.run(cmd, capture_output=True, timeout=15)
                return
            except Exception as exc:
                self.log.warning("PowerShell SAPI failed: %s. Trying pyttsx3…", exc)

            # ── Tier 4: pyttsx3 ─────────────────────────────────────────────
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 190)
                engine.setProperty("volume", 1.0)
                engine.say(clean_text)
                engine.runAndWait()
            except Exception as fatal_exc:
                self.log.error("All TTS engines failed: %s", fatal_exc)
