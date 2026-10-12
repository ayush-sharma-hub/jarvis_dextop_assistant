from __future__ import annotations
import json, threading
import pytest
from jarvis.plugins.base import ParsedOperation, Plugin, PluginResult, RiskLevel
from jarvis.plugins.notes import NotesPlugin
from jarvis.plugins.registry import PluginRegistry
from jarvis.plugins.timer import TimerPlugin

class Fake(Plugin):
    name="fake"; description="fake"; phrases=()
    def __init__(self,risk=RiskLevel.READ_ONLY,fail=False): self.risk,self.ran=risk,0; self.fail=fail
    def match(self,c): return c=="fake"
    def parse(self,c): return ParsedOperation(True,"x")
    def risk_for(self,c): return self.risk
    def describe(self,c): return "Safe description"
    def run(self,c): self.ran+=1; ( (_ for _ in ()).throw(RuntimeError()) if self.fail else None); return PluginResult("ok")

def test_registry_policy_duplicate_and_forged() -> None:
    r=PluginRegistry("confirm"); p=Fake(); r.register(p)
    with pytest.raises(ValueError): r.register(Fake())
    assert r.route("none").matched is False and r.route("fake").plugin is p
    forged=Fake(); assert not r.execute(forged,"fake",lambda _:True).ok and forged.ran==0
    assert r.execute(p,"fake",lambda _:pytest.fail("confirm")).ok and p.ran==1

def test_auto_and_declined_policy() -> None:
    r=PluginRegistry("auto"); reversible=Fake(RiskLevel.REVERSIBLE); destructive=Fake(RiskLevel.DESTRUCTIVE); destructive.name="delete"; r.register(reversible); r.register(destructive)
    assert r.execute(reversible,"fake",lambda _:pytest.fail("confirm")).ok
    assert not r.execute(destructive,"fake",lambda _:False).ok and destructive.ran==0
    disabled=PluginRegistry("disabled"); p=Fake(); disabled.register(p); assert not disabled.execute(p,"fake",lambda _:True).ok and p.ran==0

def test_malformed_plugins_are_claimed(tmp_path) -> None:
    notes=NotesPlugin(str(tmp_path/"n.json")); timer=TimerPlugin(lambda _:None)
    assert notes.match("note delete") and not notes.parse("note delete").valid
    assert notes.match("note karo") and not notes.parse("note karo").valid
    assert timer.match("timer lagao") and not timer.parse("timer lagao").valid

def test_notes_canonical_legacy_corrupt_and_delete(tmp_path) -> None:
    path=tmp_path/"notes.json"; n=NotesPlugin(str(path))
    assert n.run("note karo kal dentist").ok
    data=json.loads(path.read_text()); assert data["version"]==1 and data["notes"][0]["text"]=="kal dentist"
    assert n.parse("note delete last").kind=="delete" and n.risk_for("note delete last")==RiskLevel.DESTRUCTIVE
    path.write_text('["old"]'); assert n.run("note karo new").ok and json.loads(path.read_text())["version"]==1
    path.write_bytes(b"not-json"); assert not n.run("note karo no").ok and list(tmp_path.glob("notes.json.corrupt-*")) and path.read_bytes()==b"not-json"

class Handle:
    def __init__(self,cb): self.cb,self.cancelled=cb,False
    def cancel(self): self.cancelled=True
class Scheduler:
    def __init__(self): self.handles=[]
    def __call__(self,_,cb): h=Handle(cb); self.handles.append(h); return h

def test_timer_parsing_cap_remaining_and_shutdown() -> None:
    now=[10.0]; scheduler=Scheduler(); said=[]; t=TimerPlugin(said.append,clock=lambda:now[0],scheduler_factory=scheduler)
    for command,seconds in [("10 minute timer",600),("ek ghanta",3600),("1 hour 30 minutes",5400),("do ghante das minute",7800)]: assert t.parse(command).data["seconds"]==seconds
    for command in ("0 minute timer","-1 minute timer","timer lagao","13 hour timer"): assert not t.parse(command).valid
    assert t.run("10 minute timer").ok; now[0]=10000; assert t.run("timer kitna bacha hai").data["remaining"]==0
    t.shutdown(); assert scheduler.handles[0].cancelled; scheduler.handles[0].cb(); assert not said
    t.shutdown()

def test_timer_concurrent_cap() -> None:
    scheduler=Scheduler(); t=TimerPlugin(lambda _:None,scheduler_factory=scheduler)
    for _ in range(5): assert t.run("1 minute timer").ok
    assert not t.run("1 minute timer").ok
