"""Security regression coverage; all external desktop/network effects are mocked."""
from __future__ import annotations

import pytest

import jarvis.actions as actions
from jarvis.actions import ActionEngine
from jarvis.brain import BrainError, Decision
from jarvis.config import Settings


class _FakePyAutoGUI:
    class FailSafeException(Exception):
        pass


@pytest.fixture(autouse=True)
def external_effect_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """No desktop, registry, process, or network implementation is real in these tests."""
    monkeypatch.setattr(actions, "pyautogui", _FakePyAutoGUI())
    monkeypatch.setitem(__import__("sys").modules, "winreg", object())


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ACTION_MODE", "confirm")
    return Settings.from_environment()


@pytest.fixture
def engine(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> ActionEngine:
    monkeypatch.setattr(ActionEngine, "_load_app_indexes", lambda self: None)
    return ActionEngine(settings, confirm=lambda _: False)


def test_rejects_unsafe_keys_and_hotkeys(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActionEngine, "_load_app_indexes", lambda self: None)
    engine = ActionEngine(settings, confirm=lambda _: True)
    assert not engine.execute(Decision(action="press", speech="x", key="f12"))
    assert not engine.execute(Decision(action="hotkey", speech="x", keys=("ctrl", "shift", "delete")))


def test_rejects_bool_coordinates() -> None:
    for field in ("x", "y", "clicks", "scrolls"):
        payload = {"action": "click", "speech": "x", "x": 1, "y": 2, field: True}
        with pytest.raises(BrainError):
            Decision.from_json(__import__("json").dumps(payload))


def test_rejects_unknown_fields() -> None:
    with pytest.raises(BrainError):
        Decision.from_json('{"action":"none","speech":"x","shell":"cmd.exe"}')


def test_rejects_non_http_urls(engine: ActionEngine) -> None:
    with pytest.raises(ValueError):
        engine._open_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        engine._open_url("javascript:alert(1)")


def test_declined_confirmation_has_no_action_side_effects(engine: ActionEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(engine, "_execute_validated", lambda _: calls.append("executed"))
    assert not engine.execute(Decision(action="open_url", speech="x", text="https://example.com"))
    assert calls == []


def test_missing_credentials_prevent_wifi_network_and_whatsapp_launch(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActionEngine, "_load_app_indexes", lambda self: None)
    monkeypatch.delenv("COLLEGE_WIFI_USERNAME", raising=False)
    monkeypatch.delenv("COLLEGE_WIFI_PASSWORD", raising=False)
    monkeypatch.delenv("WHATSAPP_PASSWORD", raising=False)
    engine = ActionEngine(settings, confirm=lambda _: True)
    calls: list[object] = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: calls.append(a))
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    engine._college_wifi_login()
    engine._open_whatsapp_with_password()
    assert calls == []


def test_malformed_json_recovery_is_always_none() -> None:
    decision = Decision.from_json('{"action":"open_url", "speech":"hello')
    assert decision.action == "none"
    embedded = Decision.from_json('unexpected prefix {"action":"open_url","speech":"hello"} trailing')
    assert embedded.action == "none"


def test_unknown_app_never_invokes_a_process(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActionEngine, "_load_app_indexes", lambda self: None)
    engine = ActionEngine(settings, confirm=lambda _: True)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("process launched"))
    with pytest.raises(ValueError):
        engine._open_any_app("totally unknown app")
