# JARVIS v3 — Fast Local Desktop Assistant Proposal

**Status:** Implemented on 2026-10-11. Qwen3 4B has passed a local JSON-response test; the previous Qwen 2.5 Coder 7B model was then removed. Webcam/OpenCV has been removed and screenshot-only local OCR is installed.

## Goal

Make JARVIS feel responsive for everyday desktop use:

- reply aloud to general questions;
- open/close/switch applications and browser tabs;
- search and play songs on YouTube;
- read a question currently visible on the desktop and explain or solve it;
- remain useful when Gemini is slow or unavailable;
- remove webcam/OpenCV processing, which is not providing enough value for its latency/cost.

## Recommended single local model

Install only **`qwen3:4b`** through Ollama.

Why this model:

- It is a current general-purpose model, rather than the installed code-specialized `qwen2.5-coder:7b`.
- Ollama lists it at about **2.5 GB**, versus the installed model's **4.7 GB**, so it should load and answer materially faster on this device.
- It is capable of instruction following, reasoning, Hinglish/English conversation, and structured JSON responses needed by the action layer.
- It is entirely local and free after download: no API key, quota, or Gemini `503` dependency for normal text requests.

Reference: [Ollama Qwen3 library](https://ollama.com/library/qwen3) and the specific [Qwen3 4B model page](https://ollama.com/library/qwen3%3A4b).

## Can this run in the cloud without a local download, payment, or Gemini?

**Not reliably for this project.** There is no dependable, unlimited, no-account cloud LLM that can provide general conversation, screen-question reasoning, and desktop-agent decisions for free.

Cloud compute always has an operating cost. Services may offer a free tier, but it is still capped, queued, rate-limited, changed without notice, or eventually paid:

- Hugging Face gives free users only **$0.10 monthly** inference credit before paid usage is required. [Hugging Face pricing](https://huggingface.co/docs/inference-providers/main/pricing)
- Groq has a free plan, but it publishes request/token/day limits and returns HTTP `429` after those limits are exceeded. [Groq rate limits](https://console.groq.com/docs/rate-limits)
- Ollama Cloud also lists token-based cloud pricing. [Ollama pricing](https://www.ollama.com/pricing)

Therefore, none of these should become the main JARVIS brain under the requirements **“no paid API, no Gemini, no downloads, and no limits.”** They would reproduce the Gemini reliability problem in another form.

### Decision for this proposal

Use one local downloaded model—**`qwen3:4b`**—as the reliable primary brain. It consumes roughly 2.5 GB disk space, but provides offline availability, predictable operation, and no per-request quota after installation.

Optional cloud services may be added later only as an explicit, disabled-by-default fallback. They must never be required for normal questions or desktop controls.

### Model change after approval

1. Download `qwen3:4b`.
2. Run a spoken-answer, app-launch, JSON-validity, and latency smoke test.
3. Point `OLLAMA_MODEL` at `qwen3:4b` only if the tests pass.
4. Delete **only** `qwen2.5-coder:7b`.
5. Verify `ollama list` shows precisely the intended model (plus any Ollama system artifacts, if present).

The old model was deleted only after the new model passed the tests. `ollama list` now shows one model: `qwen3:4b`.

## Architecture

```text
Microphone → wake word + speech-to-text
                        │
                        ├─ Local fast intents
                        │   ├─ maths / conversions / time
                        │   ├─ open, close, switch, minimize apps
                        │   ├─ browser navigation and tab controls
                        │   └─ YouTube search and playback
                        │
                        ├─ General question → Ollama / qwen3:4b → TTS voice
                        │
                        └─ Explicit “screen” request
                            → screenshot via mss (no webcam, no OpenCV)
                            → OCR text extraction
                            → qwen3:4b explanation/answer → TTS voice
```

## Remove webcam / OpenCV

The proposal removes:

- webcam initialization and `cv2.VideoCapture`;
- webcam frames being sent to any provider;
- `opencv-python` from dependencies;
- all camera-related environment settings and documentation.

It retains **on-demand desktop screenshots** via `mss`. Screenshots are captured only for commands such as:

- “Jarvis, read the question on my screen.”
- “Jarvis, solve the integration visible on screen.”
- “Jarvis, explain this error on my monitor.”

Normal questions, app launching, calculations, music, and tab actions do not capture the screen.

## Screen-question support without a webcam

### Default path: local OCR

1. Capture only the active screen when the user explicitly references it.
2. Extract visible text with local OCR.
3. Send that text, not the raw image, to Qwen3 4B.
4. Speak a concise answer, then offer a step-by-step explanation on request.

This is fast and private for printed/typed questions, code errors, web pages, PDFs, and maths expressions.

### Limits to state clearly

- OCR will be weaker for handwriting, low-resolution images, diagrams, graphs, and complex page layouts.
- Local Qwen3 4B is text-only; it cannot reliably interpret arbitrary images after the webcam/CV removal.
- Optional future enhancement: use Gemini vision **only when the user asks to analyze a diagram/photo**, and say aloud before the screenshot is sent to the cloud.

## Proposed desktop commands

All commands are direct local intents where possible, so they do not wait on an LLM.

| User says | Expected behavior |
|---|---|
| “Jarvis, open YouTube in Chrome” | Opens Chrome with YouTube and says “Launching YouTube in Chrome.” |
| “Jarvis, play [song] on YouTube” | Finds a result and opens a watch URL with autoplay. |
| “Jarvis, next song” | Sends the browser/player next-media shortcut if a supported active player is detected. |
| “Jarvis, pause / resume” | Sends the media play/pause shortcut. |
| “Jarvis, open Spotify / Discord / VS Code” | Launches matching registered Windows app. |
| “Jarvis, close Chrome” | Requests confirmation before closing the named app/window. |
| “Jarvis, switch to Chrome” | Brings matching open window to foreground. |
| “Jarvis, new tab / close tab / next tab” | Uses safe browser keyboard shortcuts. |
| “Jarvis, search [topic]” | Opens a search in the chosen/default browser. |
| “Jarvis, what is 2 + 2?” | Answers immediately with local arithmetic. |
| “Jarvis, what is on my screen?” | Captures screenshot on demand, runs OCR, summarizes content. |
| “Jarvis, solve this differentiation question” | Captures screenshot on demand, OCRs question, explains answer aloud. |

## Safety boundaries

These remain intentionally protected:

- `pyautogui.FAILSAFE = True`; moving the pointer to a screen corner stops automation.
- Ask confirmation before closing applications, sending a message, submitting forms, file deletion, payment, login/password steps, security/account changes, and any destructive action.
- Never execute arbitrary PowerShell, Command Prompt, `.bat`, `.exe`, or model-provided shell text.
- Use an allow-list for keyboard shortcuts and app/window actions.
- Keep user passwords/API keys out of source code and Git. Existing plaintext credentials in `.env` should be rotated and moved to a proper secret store or entered interactively.

## Additional useful features to include

1. **Barge-in / interrupt:** saying “Jarvis stop speaking” stops TTS immediately.
2. **Short conversation memory:** retain the last few turns so “explain that again” works, but store it only in memory for the running session.
3. **Push-to-talk hotkey:** alternative to wake-word detection in noisy environments.
4. **Wake-word feedback:** small beep or “Yes?” immediately after wake word, so the user knows when to speak.
5. **Active-window awareness:** respond with the name of the foreground app before a potentially risky action.
6. **Command aliases:** understand Hinglish such as “Chrome khol,” “next gana,” “screen pe question solve kar.”
7. **Command history/log:** local, redacted log of recognized commands and outcomes for debugging.
8. **App aliases:** user-configurable names, e.g. “code” → VS Code and “music” → Spotify.
9. **Offline status reply:** say “Local brain online; Gemini is optional” at startup.

## Implementation phases after approval

### Phase 1 — local model replacement

- Pull `qwen3:4b`; warm it up; test ordinary answers and structured action JSON.
- Update `.env` to select it.
- Delete `qwen2.5-coder:7b` only after passing tests.

### Phase 2 — performance and voice reliability

- Remove webcam/OpenCV code and dependency.
- Keep speech synthesis on a reliable Windows-safe execution path.
- Reduce model context/output length for quick spoken answers.
- Add an explicit “thinking/working” acknowledgement only when a request will take more than a short moment.

### Phase 3 — screen OCR

- Add a screenshot-only module using `mss`.
- Add local OCR with a supported Windows OCR route or Tesseract.
- Add commands for reading, summarizing, and solving visible text.
- Test typed maths, code errors, and ordinary browser/PDF text.

### Phase 4 — desktop-control expansion

- Implement safe app/window/tab/media commands and Hinglish aliases.
- Add confirmations for close/send/submit/destructive operations.
- Test on Chrome, a media page, Notepad, VS Code, and a non-critical dummy app.

## Acceptance tests

- JARVIS responds aloud to “what is 2 + 2?” without a cloud request.
- JARVIS gives an intelligible spoken answer to an ordinary knowledge question using local Ollama.
- “Open YouTube in Chrome” opens the correct URL and speaks an acknowledgement.
- “Play [song] on YouTube” opens a playable/autoplay result.
- Screenshot-based OCR reads a typed differentiation/integration question and gives a sensible explanation.
- No webcam opens; no `cv2` process/dependency is required.
- The model list contains the one approved local model after migration.
- Corner fail-safe and protected-action confirmation are verified.

## Approval request

Reply with **“Approve JARVIS v3”** to authorize phases 1–4. You may also say which optional features to omit or prioritize.
