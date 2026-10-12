"""Timers with injected scheduling.

``_lock`` protects timer state and ``_stopped`` only. Callbacks mark a timer
fired under it then speak outside it. ``speech_lock`` serializes the final
check-and-speak and shutdown waits on it after setting stopped; it is never
acquired while holding ``_lock``. Thus no new speech starts after shutdown.
"""
from __future__ import annotations
import re
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol
from .base import ParsedOperation, Plugin, PluginResult, RiskLevel

class Cancellable(Protocol):
    def cancel(self) -> None: ...
def _schedule(seconds: float, callback: Callable[[], None]) -> Cancellable:
    timer = threading.Timer(seconds, callback); timer.daemon = True; timer.start(); return timer

@dataclass
class _Timer:
    deadline: float
    handle: Cancellable

class TimerPlugin(Plugin):
    name="timer"; description="Start and check timers"; phrases=("10 minute timer", "timer kitna bacha hai")
    _words={"ek":1,"do":2,"teen":3,"char":4,"chaar":4,"paanch":5,"panch":5,"chhe":6,"che":6,"saat":7,"aath":8,"nau":9,"das":10}
    def __init__(self, speak: Callable[[str],None], clock: Callable[[],float]=time.monotonic, scheduler_factory: Callable[[float,Callable[[],None]],Cancellable]=_schedule) -> None:
        self.speak,self.clock,self.scheduler_factory=speak,clock,scheduler_factory
        self._lock,self._speech_lock=threading.Lock(),threading.Lock(); self._timers: dict[str,_Timer]={}; self._latest: list[str]=[]; self._stopped=False
    def match(self,c: str) -> bool:
        s=c.strip().casefold(); return bool(re.match(r"^(?:timer\b|set\s+timer\b|(?:-?\d+|ek|do|teen|char|chaar|paanch|panch|chhe|che|saat|aath|nau|das)\s+(?:minute|min|minutes|second|seconds|hour|hours|ghanta|ghante)\b)",s))
    def parse(self,c: str) -> ParsedOperation:
        s=c.strip().casefold()
        if re.fullmatch(r"timer\s+kitna\s+(?:bacha|baaki)\s+hai",s): return ParsedOperation(True,"status")
        if re.match(r"^timer\b",s) and not re.match(r"^timer\s+lagao\b|^set\s+timer\s+for\b",s): return ParsedOperation(False,rejection="Timer command samajh nahi aaya bhai.")
        text=re.sub(r"^(?:timer\s+lagao\s*|set\s+timer\s+for\s*)", "", s).removesuffix(" ka").strip()
        pairs=re.findall(r"(-?\d+|ek|do|teen|char|chaar|paanch|panch|chhe|che|saat|aath|nau|das)\s*(seconds?|minutes?|mins?|hours?|ghanta|ghante)",text)
        if not pairs: return ParsedOperation(False,rejection="Valid timer duration bolo bhai.")
        consumed=" ".join(f"{a} {b}" for a,b in pairs)
        if not re.fullmatch(r"\s*"+re.escape(consumed).replace(r"\ ",r"\s+")+r"\s*(?:timer|ka)?\s*",text): return ParsedOperation(False,rejection="Valid timer duration bolo bhai.")
        total=0
        for raw,unit in pairs:
            value=int(raw) if raw.lstrip("-").isdigit() else self._words[raw]
            if value <= 0: return ParsedOperation(False,rejection="Timer zero ya negative nahi ho sakta bhai.")
            total += value*(3600 if unit.startswith(("hour","gh")) else 60 if unit.startswith(("min",)) else 1)
        if total > 12*3600: return ParsedOperation(False,rejection="Timer 12 ghante se bada nahi ho sakta bhai.")
        return ParsedOperation(True,"start",{"seconds":total})
    def risk_for(self,c: str) -> RiskLevel: return RiskLevel.READ_ONLY if self.parse(c).kind=="status" else RiskLevel.REVERSIBLE
    def describe(self,c: str) -> str:
        p=self.parse(c); return "Check remaining timer time" if p.kind=="status" else f"Start a {p.data.get('seconds',0)} second timer"
    def run(self,c: str) -> PluginResult:
        p=self.parse(c)
        if p.kind=="status":
            with self._lock:
                active=next((i for i in reversed(self._latest) if i in self._timers),None)
                if not active: return PluginResult("Koi active timer nahi hai bhai.")
                left=max(0,int(self._timers[active].deadline-self.clock()))
            return PluginResult(f"Timer mein {left} seconds baaki hain bhai.",data={"remaining":left})
        with self._lock:
            if self._stopped: return PluginResult("Timer service band hai bhai.",False)
            if len(self._timers)>=5: return PluginResult("Ek saath sirf 5 timers laga sakte hain bhai.",False)
            ident=uuid.uuid4().hex; deadline=self.clock()+p.data["seconds"]
            def fired() -> None:
                with self._lock:
                    if self._stopped or ident not in self._timers: return
                    self._timers.pop(ident); self._latest=[x for x in self._latest if x!=ident]
                with self._speech_lock:
                    with self._lock:
                        if self._stopped: return
                    self.speak("Timer khatam ho gaya bhai!")
            handle=self.scheduler_factory(p.data["seconds"],fired); self._timers[ident]=_Timer(deadline,handle); self._latest.append(ident)
        return PluginResult(f"{p.data['seconds']} seconds ka timer laga diya bhai.")
    def shutdown(self) -> None:
        with self._lock:
            if self._stopped: return
            self._stopped=True; handles=[t.handle for t in self._timers.values()]; self._timers.clear(); self._latest.clear()
        for handle in handles:
            try: handle.cancel()
            except Exception as exc: logging.getLogger(self.__class__.__name__).debug("Timer cancellation failed: %s", exc)
        with self._speech_lock: pass
