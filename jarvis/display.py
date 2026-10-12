"""
Rich animated terminal display for JARVIS — safe ASCII characters and robust layout.
Includes type-ignore guards and fallbacks for zero Pylance warnings.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Optional

try:
    from rich import box  # type: ignore
    from rich.console import Console  # type: ignore
    from rich.layout import Layout  # type: ignore
    from rich.live import Live  # type: ignore
    from rich.panel import Panel  # type: ignore
    from rich.table import Table  # type: ignore
    from rich.text import Text  # type: ignore
    HAS_RICH = True
except Exception:
    HAS_RICH = False
    box = None  # type: ignore
    Console = None  # type: ignore
    Layout = None  # type: ignore
    Live = None  # type: ignore
    Panel = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore

log = logging.getLogger(__name__)

console: Any = Console(safe_box=True) if HAS_RICH and Console else None

JARVIS_BANNER = """[bold cyan]
      _    _    ____  __     __ ___ ____  
     | |  / \  |  _ \ \ \   / /|_ _/ ___| 
  _  | | / _ \ | |_) | \ \ / /  | |\___ \ 
 | |_| |/ ___ \|  _ <   \ V /   | | ___) |
  \___//_/   \_\_| \_\   \_/   |___|____/ 
[/bold cyan]
[bold white]  J.A.R.V.I.S. Multi-Modal Desktop AI Assistant[/bold white]
[dim cyan]  RIT Roorkee  --  Manthan AI Hackathon 2026[/dim cyan]"""

_STATE_COLORS = {
    "STANDBY": "dim cyan",
    "LISTENING": "bold green",
    "THINKING": "bold yellow",
    "SPEAKING": "bold cyan",
    "ACTING": "bold magenta",
    "ERROR": "bold red",
}

_WAVE_CHARS = ["-", "=", "#", "X", "#", "=", "-"]


class JarvisDisplay:
    """Rich-based live terminal interface for JARVIS."""

    def __init__(self) -> None:
        self._state = "STANDBY"
        self._state_detail = "Say 'Hey Jarvis' or start speaking"
        self._log: list[tuple[str, str, str]] = []
        self._frame = 0
        self._lock = threading.RLock()
        self._running = False
        self._providers: list[str] = []
        self._voice = "ryan (edge-tts)"
        self._sys_stats: dict[str, Any] = {}
        self._user_name = "Ayush"

    def set_info(self, providers: tuple[str, ...], voice: str, user_name: str = "Ayush") -> None:
        self._providers = list(providers)
        self._voice = voice
        self._user_name = user_name

    def update_state(self, state: str, detail: str = "") -> None:
        with self._lock:
            self._state = state
            if detail:
                self._state_detail = detail

    def add_log(self, role: str, text: str) -> None:
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self._log.append((ts, role, text[:160]))
            if len(self._log) > 25:
                self._log.pop(0)

    def update_sys_stats(self, stats: dict[str, Any]) -> None:
        with self._lock:
            self._sys_stats = stats

    def _render_status(self) -> Any:
        if not HAS_RICH or not Text or not Panel:
            return None
        state = self._state
        color = _STATE_COLORS.get(state, "white")
        frame_idx = self._frame % len(_WAVE_CHARS)

        if state == "LISTENING":
            wave = " ".join(_WAVE_CHARS[(frame_idx + i) % len(_WAVE_CHARS)] for i in range(7))
            indicator = Text(f" [{wave}] LISTENING FOR COMMAND", style="bold green")
        elif state == "THINKING":
            dots = "." * (self._frame % 4 + 1)
            indicator = Text(f" [*] Neural Reasoning In Progress{dots}", style="bold yellow")
        elif state == "SPEAKING":
            indicator = Text(" (o) Vocalizing Neural Response...", style="bold cyan")
        elif state == "ACTING":
            indicator = Text(" [!] Executing Desktop Action...", style="bold magenta")
        elif state == "ERROR":
            indicator = Text(" [X] Error Encountered", style="bold red")
        else:
            indicator = Text(f" (-) Active Standby -- Listening ({self._user_name})", style="dim cyan")

        content = Text()
        content.append(" STATE: ", style="bold dim")
        content.append(f"[{state}] ", style=color)
        content.append_text(indicator)
        content.append(f"\n {self._state_detail}", style="dim white")

        return Panel(content, title="[bold cyan] SYSTEM STATUS [/bold cyan]", border_style="cyan", box=box.ASCII if box else None)

    def _render_log(self) -> Any:
        if not HAS_RICH or not Table or not Text or not Panel:
            return None
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("time", style="dim", width=9)
        table.add_column("role", width=10)
        table.add_column("text", ratio=1)

        with self._lock:
            entries = list(self._log[-10:])

        if not entries:
            table.add_row("--:--:--", Text("SYSTEM", style="dim"), Text("Listening for your voice...", style="dim"))
        else:
            for ts, role, text in entries:
                if role == "USER":
                    table.add_row(ts, Text("YOU", style="bold green"), Text(text, style="white"))
                elif role == "JARVIS":
                    table.add_row(ts, Text("JARVIS", style="bold cyan"), Text(text, style="cyan"))
                elif role == "ACTION":
                    table.add_row(ts, Text("ACTION", style="bold magenta"), Text(text, style="magenta"))
                else:
                    table.add_row(ts, Text(role, style="dim yellow"), Text(text, style="dim"))

        return Panel(table, title="[bold cyan] CONVERSATION & ACTIONS [/bold cyan]", border_style="cyan", box=box.ASCII if box else None)

    def _render_info(self) -> Any:
        if not HAS_RICH or not Text or not Panel:
            return None
        lines = Text()
        lines.append(f" User: {self._user_name} (RIT Roorkee)  |  ", style="bold yellow")
        lines.append(f"Voice: {self._voice}  |  ", style="bold cyan")
        lines.append("Brain: ", style="dim")
        for p in self._providers:
            lines.append(f"{p} ", style="bold green")

        stats = self._sys_stats
        if stats:
            cpu = stats.get("cpu", 0)
            ram = stats.get("ram_pct", 0)
            lines.append(f"\n CPU: {cpu:.0f}%  |  RAM: {ram:.0f}%", style="dim")
            if "bat" in stats and stats["bat"] is not None:
                lines.append(f"  |  Battery: {stats['bat']}%", style="dim")

        return Panel(lines, title="[bold cyan] SYSTEM TELEMETRY [/bold cyan]", border_style="cyan", box=box.ASCII if box else None)

    def _make_layout(self) -> Any:
        if not HAS_RICH or not Layout:
            return None
        layout = Layout()
        layout.split_column(
            Layout(name="status", size=4),
            Layout(name="log", ratio=1),
            Layout(name="info", size=4),
        )
        with self._lock:
            layout["status"].update(self._render_status())
            layout["log"].update(self._render_log())
            layout["info"].update(self._render_info())
        self._frame += 1
        return layout

    def start(self) -> None:
        if HAS_RICH and console:
            try:
                console.print(JARVIS_BANNER)
            except Exception:
                self._print_plain_banner()
        else:
            self._print_plain_banner()

        self._running = True
        if HAS_RICH and Live:
            t = threading.Thread(target=self._render_loop, daemon=True)
            t.start()

    @staticmethod
    def _print_plain_banner() -> None:
        print("==================================================")
        print("  J.A.R.V.I.S. Multi-Modal Desktop AI Assistant")
        print("  RIT Roorkee -- Manthan AI Hackathon 2026")
        print("==================================================")

    def _render_loop(self) -> None:
        if not HAS_RICH or not Live or not console:
            return
        try:
            with Live(self._make_layout(), console=console, refresh_per_second=4, screen=False) as live:
                while self._running:
                    live.update(self._make_layout())
                    time.sleep(0.25)
        except Exception as exc:
            log.debug("Live render ended: %s", exc)

    def stop(self) -> None:
        self._running = False
        time.sleep(0.3)


display = JarvisDisplay()