import pytest

from jarvis.brain import BrainError, Decision, FreeWebBrain


def test_parses_safe_answer() -> None:
    decision = Decision.from_json('{"action":"none","speech":"At once, sir."}')
    assert decision.action == "none"
    assert decision.speech == "At once, sir."


def test_parses_multimedia_and_app_actions() -> None:
    play = Decision.from_json('{"action":"play_youtube","speech":"Playing music, sir.","text":"seedhe maut"}')
    assert play.action == "play_youtube"
    assert play.text == "seedhe maut"

    app = Decision.from_json('{"action":"open_named_app","speech":"Opening Spotify, sir.","app":"spotify"}')
    assert app.action == "open_named_app"
    assert app.app == "spotify"


def test_rejects_unknown_or_incomplete_action_fields() -> None:
    with pytest.raises(BrainError):
        Decision.from_json('{"action":"click","speech":"Done","command":"del *"}')
    with pytest.raises(BrainError):
        Decision.from_json('{"action":"click","speech":"Done"}')


def test_free_web_brain() -> None:
    fw = FreeWebBrain()
    raw = fw.complete("what is python")
    decision = Decision.from_json(raw)
    assert decision.speech
    assert len(decision.speech) > 5
