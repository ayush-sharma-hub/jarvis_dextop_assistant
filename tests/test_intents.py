from jarvis.intents import LocalIntentRouter


def test_youtube_commands_do_not_need_an_llm() -> None:
    router = LocalIntentRouter()
    open_youtube = router.route("can you open YouTube")
    play_song = router.route("play bohemian rhapsody on youtube")

    assert open_youtube is not None
    assert open_youtube.action == "open_url"
    assert open_youtube.text == "https://www.youtube.com/"
    assert play_song is not None
    assert play_song.action == "play_youtube"
    assert play_song.text == "bohemian rhapsody"


def test_youtube_in_chrome_and_math_are_local() -> None:
    router = LocalIntentRouter()
    chrome = router.route("open YouTube on Chrome")
    math = router.route("what is 2 plus 2")

    assert chrome is not None
    assert chrome.action == "open_url_in_chrome"
    assert math is not None
    assert math.action == "none"
    # New Hinglish speech - just check result contains "4"
    assert math.speech is not None
    assert "4" in math.speech


def test_compound_youtube_command() -> None:
    router = LocalIntentRouter()
    decision = router.route("hey jarvis open youtube and play seedhe maut")

    assert decision is not None
    assert decision.action == "play_youtube"
    assert decision.text == "seedhe maut"
    assert "Seedhe Maut" in decision.speech


def test_installed_application_uses_local_launcher() -> None:
    router = LocalIntentRouter()
    chrome = router.route("open Google Chrome")
    spotify = router.route("open Spotify")
    powershell = router.route("open PowerShell")

    assert chrome is not None
    assert chrome.action == "open_named_app"
    assert spotify is not None
    assert spotify.action == "open_named_app"
    assert powershell is not None
    assert powershell.action == "open_named_app"


def test_volume_and_time_commands() -> None:
    router = LocalIntentRouter()
    vol_up = router.route("volume up")
    time_cmd = router.route("what time is it")

    assert vol_up is not None
    assert vol_up.action == "volume_up"
    assert time_cmd is not None
    assert time_cmd.action == "none"
    # Hinglish speech - check for time-related words
    speech_lower = time_cmd.speech.lower()
    assert any(word in speech_lower for word in ["baj", "am", "pm", "time", "bhai"])


def test_hinglish_commands_route_locally() -> None:
    router = LocalIntentRouter()

    time_cmd = router.route("kya time hai")
    assert time_cmd is not None
    assert time_cmd.action == "none"
    assert "baj" in time_cmd.speech.lower() or "pm" in time_cmd.speech.lower() or "am" in time_cmd.speech.lower()

    battery_cmd = router.route("battery kitni hai")
    assert battery_cmd is not None
    assert battery_cmd.action == "none"

    gaana_cmd = router.route("gaana laga shape of you")
    assert gaana_cmd is not None
    assert gaana_cmd.action == "play_youtube"
    assert "shape of you" in gaana_cmd.text.lower()

    volume_cmd = router.route("volume badha")
    assert volume_cmd is not None
    assert volume_cmd.action == "volume_up"

    whatsapp_cmd = router.route("open whatsapp")
    assert whatsapp_cmd is not None
    assert whatsapp_cmd.action == "open_whatsapp"


def test_companion_emotion_detection() -> None:
    from jarvis.companion import get_companion
    companion = get_companion()

    sad = companion.detect_emotion("yaar main bahut sad hun")
    assert sad.detected is True
    assert sad.emotion == "sad"
    assert sad.response is not None

    stressed = companion.detect_emotion("main bahut stressed hun exam ke liye")
    assert stressed.detected is True

    neutral = companion.detect_emotion("open youtube please")
    assert neutral.detected is False
    assert neutral.emotion == "neutral"
