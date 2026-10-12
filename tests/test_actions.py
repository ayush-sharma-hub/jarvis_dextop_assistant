import pytest

from jarvis.actions import ActionEngine, COMMON_APP_COMMANDS
from jarvis.brain import Decision
from jarvis.config import Settings


def test_action_engine_initializes_and_indexes() -> None:
    settings = Settings.from_environment()
    engine = ActionEngine(settings)
    assert len(engine._shortcut_apps) > 0 or len(engine._registry_apps) > 0
    assert "notepad" in COMMON_APP_COMMANDS


def test_action_engine_none_action_returns_true() -> None:
    settings = Settings.from_environment()
    engine = ActionEngine(settings)
    assert engine.execute(Decision(action="none", speech="Hello, sir.")) is True
