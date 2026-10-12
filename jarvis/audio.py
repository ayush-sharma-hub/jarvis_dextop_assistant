"""Microphone input and wake-word-aware speech recognition with conversational follow-up."""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import speech_recognition as sr

from .config import Settings


class AudioModule:
    """Continuously listen for audio and extract user commands with active follow-up window."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__name__)
        self.recognizer = sr.Recognizer()

        # Dynamic sensitivity & ambient adjustment
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5

        # CRITICAL FIX for command cutting off halfway:
        # 1.0s pause threshold gives natural breathing/thinking room so "my name is ayush" doesn't get clipped
        self.recognizer.pause_threshold = 1.0
        self.recognizer.phrase_threshold = 0.2
        self.recognizer.non_speaking_duration = 0.6

        # Sort wake words longest-first so "hey jarvis" matches before "jarvis"
        self.wake_words = sorted(settings.wake_words, key=len, reverse=True)

        # Conversational follow-up window (timestamp until which wake word is optional)
        self._followup_until: float = 0.0
        self._followup_seconds: float = 12.0

        self.microphone = sr.Microphone(device_index=settings.microphone_index)
        with self.microphone as source:
            self.log.info("Calibrating microphone for ambient noise…")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
            # Ensure energy threshold is in a healthy range (not deaf, not too sensitive)
            self.recognizer.energy_threshold = max(200, min(self.recognizer.energy_threshold, 1500))

    def extend_followup(self, seconds: float = 12.0) -> None:
        """Keep JARVIS active so the user can speak without repeating the wake word."""
        self._followup_until = time.time() + seconds

    def clear_followup(self) -> None:
        """Reset the active window back to standby mode."""
        self._followup_until = 0.0

    @property
    def is_in_followup(self) -> bool:
        return time.time() < self._followup_until

    def listen_for_command(self) -> Optional[str]:
        """Listen and return spoken command. Supports wake word and conversational follow-up."""
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.settings.command_timeout_seconds,
                    phrase_time_limit=self.settings.phrase_time_limit_seconds,
                )

            # Recognize with Indian English (en-IN) for accurate Indian names & accents,
            # falling back to en-US if needed
            transcript = ""
            try:
                transcript = str(self.recognizer.recognize_google(audio, language="en-IN")).strip()
            except sr.UnknownValueError:
                try:
                    transcript = str(self.recognizer.recognize_google(audio, language="en-US")).strip()
                except Exception:
                    return None
            except Exception:
                try:
                    transcript = str(self.recognizer.recognize_google(audio, language="en-US")).strip()
                except Exception:
                    return None

            if not transcript:
                return None

            self.log.debug("Heard raw transcript: %r", transcript)

        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            self.log.warning("Speech recognition service error: %s", exc)
            return None

        lower = transcript.lower()

        # 1. Check for explicit wake word in sentence (e.g. "Jarvis my name is Ayush")
        for word in self.wake_words:
            pos = lower.find(word)
            if pos >= 0:
                raw_command = transcript[pos + len(word):].strip(" ,.!?:;")
                command = self._clean_command(raw_command)
                self.extend_followup()
                self.log.info("Wake word detected: %s | Command: %r", word, command or "yes")
                return command or "yes"

        # 2. Check for wake greetings like "hey jarvis", "hi jarvis", etc.
        match = re.search(r"\b(?:hey|hi|hello|ok|okay)\s+(?:jarvis|friday)\b", lower)
        if match:
            raw_command = transcript[match.end():].strip(" ,.!?:;")
            command = self._clean_command(raw_command)
            self.extend_followup()
            self.log.info("Wake greeting detected | Command: %r", command or "yes")
            return command or "yes"

        # 3. Conversational Follow-Up: If recently active, accept command without repeating "Jarvis"
        if self.is_in_followup:
            command = self._clean_command(transcript)
            if command:
                self.extend_followup()
                self.log.info("Follow-up active | Command: %r", command)
                return command

        return None

    @staticmethod
    def _clean_command(raw: str) -> str:
        """Strip polite prefixes and extraneous punctuation."""
        return re.sub(
            r"^(?:can you\s+|could you\s+|please\s+|will you\s+|just\s+)+",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip(" ,.!?:;")