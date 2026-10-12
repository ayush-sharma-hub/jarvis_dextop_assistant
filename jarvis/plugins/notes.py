"""Atomic local notes storage."""
from __future__ import annotations
import json, logging, os, re, shutil, tempfile, threading
from datetime import datetime, timezone
from pathlib import Path
from .base import ParsedOperation, Plugin, PluginResult, RiskLevel

class NotesPlugin(Plugin):
    name="notes"; description="Save, read, and delete local notes"; phrases=("note karo ...", "mere notes padho", "note delete last")
    def __init__(self, path: str|None=None) -> None:
        self.path=Path(path or os.getenv("JARVIS_NOTES_FILE", "./data/notes.json")); self._lock=threading.Lock(); self.log=logging.getLogger(self.__class__.__name__)
    def match(self,c: str) -> bool:
        return bool(re.match(r"^(?:note\s+(?:delete\b|karo\b|likh\s+lo\b)|last\s+note\s+delete\b|mere\s+notes\s+padho\b|last\s+note\s+batao\b)",c.strip().casefold()))
    def parse(self,c: str) -> ParsedOperation:
        s=c.strip()
        low=s.casefold()
        if re.fullmatch(r"(?:note\s+delete\s+last|last\s+note\s+delete\s+karo?)",low): return ParsedOperation(True,"delete")
        if low.startswith("note delete") or low.startswith("last note delete"): return ParsedOperation(False,rejection="Sirf last note delete kar sakta hun bhai.")
        if re.fullmatch(r"(?:mere\s+notes\s+padho|last\s+note\s+batao)",low): return ParsedOperation(True,"read")
        m=re.match(r"^(?:note\s+karo|note\s+likh\s+lo)\s*(.*)$",s,re.I)
        if m:
            text=m.group(1).strip()
            if not text: return ParsedOperation(False,rejection="Note mein kya likhna hai bhai?")
            if len(text)>1000: return ParsedOperation(False,rejection="Note 1000 characters se chhota rakho bhai.")
            return ParsedOperation(True,"save",{"text":text})
        return ParsedOperation(False,rejection="Notes command samajh nahi aaya bhai.")
    def risk_for(self,c: str) -> RiskLevel:
        return {"read":RiskLevel.READ_ONLY,"save":RiskLevel.REVERSIBLE,"delete":RiskLevel.DESTRUCTIVE}.get(self.parse(c).kind,RiskLevel.READ_ONLY)
    def describe(self,c: str) -> str:
        p=self.parse(c)
        if p.kind=="delete": return "Delete the most recent note"
        if p.kind=="save":
            safe=re.sub(r"(?i)\b(password|passcode|token|api[_ -]?key)\s*[:=]?\s*\S+", r"\1 [redacted]", p.data["text"][:80])
            return f'Save a note: "{safe}"'
        return "Read saved notes"
    def _read(self) -> tuple[list[dict[str,str]],bool]:
        if not self.path.exists(): return [],False
        raw=self.path.read_bytes()
        try: data=json.loads(raw.decode("utf-8"))
        except Exception: self._corrupt(raw); raise ValueError("corrupt")
        legacy=False
        if isinstance(data,dict) and data.get("version")==1 and isinstance(data.get("notes"),list): notes=data["notes"]
        elif isinstance(data,list):
            legacy=True; notes=[{"text":v,"created_at":""} if isinstance(v,str) else v for v in data]
        else: self._corrupt(raw); raise ValueError("corrupt")
        if not all(isinstance(v,dict) and isinstance(v.get("text"),str) and isinstance(v.get("created_at"),str) and 1<=len(v["text"])<=1000 for v in notes): self._corrupt(raw); raise ValueError("corrupt")
        return notes,legacy
    def _corrupt(self,raw: bytes) -> None:
        backup=self.path.with_name(self.path.name+".corrupt-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        try: backup.write_bytes(raw); self.log.error("Corrupt notes backed up to %s",backup)
        except Exception as exc: self.log.error("Could not back up corrupt notes: %s",exc)
    def _write(self,notes: list[dict[str,str]]) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix=".notes-",suffix=".tmp")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump({"version":1,"notes":notes},f,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    def run(self,c: str) -> PluginResult:
        p=self.parse(c)
        with self._lock:
            try: notes,_=self._read()
            except (OSError,ValueError): return PluginResult("Notes file corrupt ya unreadable hai; maine use nahi badla bhai.",False)
            if p.kind=="read": return PluginResult("Koi note nahi hai bhai." if not notes else "Latest note: "+notes[-1]["text"],data={"notes":notes})
            if p.kind=="delete":
                if not notes: return PluginResult("Koi note nahi hai bhai.")
                notes.pop(); self._write(notes); return PluginResult("Last note delete kar diya bhai.")
            if len(notes)>=500: return PluginResult("500 notes ki limit aa gayi bhai.",False)
            notes.append({"text":p.data["text"],"created_at":datetime.now(timezone.utc).isoformat()}); self._write(notes); return PluginResult("Note save kar diya bhai.")
