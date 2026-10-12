"""
J.A.R.V.I.S. — Just A Rather Very Intelligent System
Multi-Modal Neural Voice Desktop Assistant
RIT Roorkee · Manthan AI Hackathon 2026
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request

from dotenv import load_dotenv

from jarvis.actions import ActionEngine
from jarvis.audio import AudioModule
from jarvis.brain import BrainError, Decision, FailoverBrain
from jarvis.companion import get_companion
from jarvis.config import Settings
from jarvis.display import display
from jarvis.intents import LocalIntentRouter
from jarvis.memory import ConversationMemory
from jarvis.speech import SpeechModule
from jarvis.vision import VisionModule


def configure_logging() -> None:
    """Send library logs to jarvis.log so the animated terminal display stays clean."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler("jarvis.log", encoding="utf-8"),
        ],
    )


def _ensure_ollama_running(ollama_url: str = "http://127.0.0.1:11434") -> None:
    """Ensure Ollama local AI server is active on GPU; auto-start if down."""
    try:
        with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=1.0) as resp:
            if resp.status == 200:
                return
    except Exception:
        pass

    ollama_exe = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if os.path.exists(ollama_exe):
        try:
            subprocess.Popen([ollama_exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            for _ in range(8):
                time.sleep(0.5)
                try:
                    with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=0.5) as resp:
                        if resp.status == 200:
                            logging.info("Ollama engine auto-started successfully on GPU.")
                            return
                except Exception:
                    pass
        except Exception as exc:
            logging.warning("Could not auto-start Ollama: %s", exc)


def _stats_worker(stop_event: threading.Event) -> None:
    """Background telemetry thread for CPU, RAM, and Battery updates."""
    try:
        import psutil
        while not stop_event.is_set():
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                bat = psutil.sensors_battery()
                display.update_sys_stats({
                    "cpu": cpu,
                    "ram_pct": mem.percent,
                    "bat": int(bat.percent) if bat else None,
                })
            except Exception:
                pass
            stop_event.wait(4)
    except ImportError:
        pass


def run() -> None:
    """Run the continuous wake-word -> audio -> reasoning -> action & speech loop."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()
    settings = Settings.from_environment()

    # 0. Ensure Ollama local AI is running on GPU
    _ensure_ollama_running(settings.ollama_url)

    # 1. Initialize core modules
    mouth = SpeechModule(rate=settings.tts_rate, voice_name=settings.tts_voice)
    hands = ActionEngine(settings)
    memory = ConversationMemory()
    local_intents = LocalIntentRouter(memory=memory)
    brain = FailoverBrain(settings)
    audio = AudioModule(settings)
    vision = VisionModule(settings)
    companion = get_companion()

    # 2. Start animated terminal display. Camera/gesture tracking is intentionally
    # absent: screenshots are captured only after an explicit screen request.
    display.set_info(brain.available_providers, settings.tts_voice or "madhur", user_name=memory.user_name)
    display.start()
    display.add_log("SYSTEM", f"Online · User: {memory.user_name} · RIT Roorkee · Voice: Madhur")

    # 3. Start telemetry background thread
    stop_stats = threading.Event()
    stats_thread = threading.Thread(target=_stats_worker, args=(stop_stats,), daemon=True)
    stats_thread.start()

    # 4. Welcome vocalization — Natural Indian Hinglish
    display.update_state("SPEAKING", f"Greeting {memory.user_name}")
    greeting = companion.greeting_of_day(memory.user_name)
    mouth.speak(greeting)
    display.add_log("JARVIS", greeting)
    audio.extend_followup(12.0)

    try:
        while True:
            # Update display state
            if audio.is_in_followup:
                display.update_state("LISTENING", "Baat karo bhai — sun raha hun!")
            else:
                display.update_state("STANDBY", f"Waiting for wake word ({', '.join(settings.wake_words)})")

            command = audio.listen_for_command()
            if not command:
                continue

            # Check shutdown commands
            clean_cmd = command.lower().strip(" .,!?:;")
            if clean_cmd in {"stop", "quit", "exit", "shutdown", "bye", "goodbye", "power off", "band kar", "band ho ja", "so ja"}:
                display.update_state("SPEAKING", "Shutting down")
                farewell = f"Theek hai {memory.user_name} bhai! Kaam khatam. Phir milenge — JARVIS out!"
                display.add_log("USER", command)
                display.add_log("JARVIS", farewell)
                mouth.speak(farewell)
                memory.save_persistent()
                break

            display.add_log("USER", command)
            display.update_state("THINKING", f"Processing: \"{command}\"")

            # Screen questions are OCR'd locally; raw screenshots are not sent to a cloud
            # provider. The extracted text is then answered by the local Ollama model.
            lower_cmd = command.lower()
            if command_needs_visual_context(command):
                ocr_text = vision.read_screen_text()
                if ocr_text.startswith("Local screen OCR") or ocr_text.startswith("I could not"):
                    display.update_state("SPEAKING", "OCR unavailable")
                    display.add_log("JARVIS", ocr_text)
                    mouth.speak(ocr_text)
                    continue
                command = f"{command}\n\nVisible screen text (OCR):\n{ocr_text}"
                display.add_log("SCREEN OCR", ocr_text[:240])

            # Check for emotional content FIRST — highest priority
            emotion_result = companion.detect_emotion(command)
            if emotion_result.detected and emotion_result.response:
                display.update_state("SPEAKING", f"Emotional support: {emotion_result.emotion}")
                display.add_log("JARVIS", emotion_result.response)
                mouth.speak(emotion_result.response)
                memory.add_turn(command, emotion_result.response)
                audio.extend_followup(20.0)
                continue

            # Check for conversational banter
            if companion.is_conversational(command) and len(command.split()) < 8:
                conv_reply = companion.conversational_reply(command)
                display.update_state("SPEAKING", "Conversation mode")
                display.add_log("JARVIS", conv_reply)
                mouth.speak(conv_reply)
                memory.add_turn(command, conv_reply)
                audio.extend_followup(15.0)
                continue

            # Step 1: Zero-latency Local Intent Router
            decision = local_intents.route(command)

            # Step 2: Fall back to AI Brain (Ollama on GPU primary)
            if decision is None:
                if not brain.available_providers:
                    decision = local_intents.route("help")
                    if decision is None:
                        fallback_msg = "Yaar, local AI engine offline hai. Local desktop commands kaam kar rahe hain!"
                        mouth.speak(fallback_msg)
                        continue

                # Screen content has already been supplied as local OCR text.
                context = None
                try:
                    mem_block = memory.build_context_block()
                    decision = brain.decide(command, context, memory_context=mem_block)
                except BrainError as exc:
                    logging.error("Brain reasoning failure: %s", exc)
                    display.update_state("ERROR", "Brain timeout")
                    mouth.speak("Yaar, AI response mein thoda lag aa gaya. Ek baar phir bolo please!")
                    continue

            # Handle fact-remembering action from LLM
            if decision.action == "remember_fact" and decision.text:
                memory.remember_fact(decision.text)
                display.add_log("SYSTEM", f"Stored fact: {decision.text}")

            # Step 3: Vocalize speech
            if decision.speech:
                display.add_log("JARVIS", decision.speech)
                display.update_state("SPEAKING", decision.speech[:60])
                mouth.speak(decision.speech)

            # Step 4: Execute desktop / network action in background
            if decision.action != "none":
                display.add_log("ACTION", f"Executing {decision.action}")
                display.update_state("ACTING", f"Action: {decision.action}")
                threading.Thread(target=hands.execute, args=(decision,), daemon=True).start()
                time.sleep(0.3)

            # Record turn in conversation memory
            memory.add_turn(command, decision.speech)
            # Extend conversation window
            audio.extend_followup(15.0)

    finally:
        stop_stats.set()
        vision.close()
        display.stop()
        memory.save_persistent()


def command_needs_visual_context(command: str) -> bool:
    """Return true only when a spoken request explicitly refers to visible screen/camera."""
    text = command.casefold()
    triggers = (
        "screen", "monitor", "display", "webcam", "camera", "image", "photo",
        "what do you see", "look at", "visible", "on my desktop", "this error",
    )
    return any(trigger in text for trigger in triggers)


if __name__ == "__main__":
    configure_logging()
    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        run()
    except KeyboardInterrupt:
        print("\nJ.A.R.V.I.S. stopped by user.")
        sys.exit(0)
    except Exception as exc:
        logging.exception("Fatal startup error: %s", exc)
        print(f"\n[FATAL ERROR]: {exc}")
        sys.exit(1)
