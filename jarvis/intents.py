"""
Fast local intent router - handles the vast majority of commands with ZERO API calls.
Gen-Z Hinglish personality - casual, cool, relatable. No more formal "sir".
"""

from __future__ import annotations

import ast
import json
import random
import re
import socket
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

from .brain import Decision


_GREETINGS = [
    "Haan bhai, bol! Kya scene hai?",
    "Main ready hun yaar. Kya karna hai?",
    "JARVIS online, full power mein! Bata kya chahiye.",
    "Haan bolo! Sunna ho raha hai.",
    "Aye bhai! Kya hukum hai aaj?",
]

_HOW_ARE_YOU = [
    "Ekdum mast hun yaar! GPU garam hai, code ready hai. Tu batao kya chal raha?",
    "Main toh always on point hun bhai. 0% sad, 100% ready. Teri sun.",
    "Yaar, AI hun toh feelings nahi hain technically, but conversation mein mazaa aata hai! Kya hai plan?",
    "Full operational mode mein hun bro. Koi glitch nahi, koi lag nahi. Bol kya karna hai.",
]

_JOKES = [
    "Yaar ek programmer se pucha life kaisi hai? Bola 404: Happiness Not Found. Relatable nahi?",
    "Bhai, JavaScript developer sad kyun tha? Kyunki woh null kar gaya apni feelings ko. Classic.",
    "Why do programmers prefer dark mode? Light attracts bugs yaar. Simple logic.",
    "Bro, git commit -m Finally fixed it ke baad phir same bug aaye toh - git cry.",
    "Yaar AI hone ka ek fayda hai - kabhi bhi exam nahi dena padta. No cap.",
]

_COMPLIMENTS = [
    "Aww yaar, thanks! Tu bhi solid hai honestly.",
    "Bhai, teri baat sunke motivation milta hai. Karte raho!",
    "Accha lagta hai yaar jab appreciate karo. Tu bhi keep it up bhai!",
    "Hahaha, shukriya! Now let us get back to work - kya karna hai next?",
]

_CAPABILITIES = (
    "Bhai, yeh sab kar sakta hun main:\n"
    "- Koi bhi app open karna - Chrome, Spotify, VS Code, Discord aur bahut kuch\n"
    "- YouTube pe koi bhi gaana ya video play karna\n"
    "- Google pe search karna\n"
    "- Volume, media controls handle karna\n"
    "- Kisi bhi topic pe questions ka jawab dena\n"
    "- Time, date, weather batana\n"
    "- Math calculate karna\n"
    "- Battery, CPU, RAM status check karna\n"
    "- College WiFi login karna automatically\n"
    "- WhatsApp kholna auto-password ke saath\n"
    "Bas bolo - main handle kar lunga!"
)


class LocalIntentRouter:
    """Map spoken commands to instant local actions with zero latency. Gen-Z Hinglish personality."""

    def __init__(self, memory: Any = None) -> None:
        self._memory = memory

    _ALIASES = {
        "browser": "browser", "web browser": "browser",
        "google": "chrome", "chrome": "chrome", "google chrome": "chrome",
        "notepad": "notepad", "calculator": "calculator", "calc": "calculator",
        "file explorer": "explorer", "files": "explorer", "explorer": "explorer",
        "settings": "settings", "windows settings": "settings",
        "task manager": "task manager", "taskmgr": "task manager",
        "cmd": "cmd", "command prompt": "cmd",
        "powershell": "powershell", "terminal": "terminal", "windows terminal": "terminal",
        "spotify": "spotify", "discord": "discord", "steam": "steam",
        "whatsapp": "whatsapp", "code": "code", "vscode": "code",
        "vs code": "code", "visual studio code": "code",
        "paint": "paint", "word": "word", "excel": "excel", "powerpoint": "powerpoint",
    }

    def route(self, command: str) -> Decision | None:
        original = command.strip()
        normalized = self._normalize(original)
        if not normalized:
            return None

        # WiFi Login
        if re.search(
            r"\b(?:wifi login|login (?:to )?(?:rit|college|campus|wifi)|connect (?:to )?(?:rit|college|campus|wifi)|rit roorkee|college wifi|rit wifi|open wifi|college net|campus net|wifi connect karo|wifi pe login|college ka wifi)\b",
            normalized,
        ):
            user_name = self._memory.user_name if (self._memory and hasattr(self._memory, "user_name")) else "Ayush"
            return Decision(
                action="college_wifi_login",
                speech=f"RIT ka WiFi login shuru kar raha hun {user_name} bhai!",
            )

        # WhatsApp with auto-password
        if re.search(
            r"\b(?:open whatsapp|start whatsapp|launch whatsapp|whatsapp khol|whatsapp kholde|whatsapp kholdo)\b",
            normalized,
        ):
            return Decision(
                action="open_whatsapp",
                app="whatsapp",
                speech="WhatsApp khol raha hun bhai - password bhi daal dunga apne aap!",
            )

        # User Name
        name_match = re.match(
            r"^(?:my name is|i am|call me|myself|mera naam hai|mujhe bulao|main hun)\s+([a-zA-Z]+)(?:\s+.*)?$",
            normalized,
        )
        if name_match:
            new_name = name_match.group(1).title()
            if self._memory and hasattr(self._memory, "set_user_name"):
                self._memory.set_user_name(new_name)
            return Decision(
                action="remember_fact",
                text=f"user_name={new_name}",
                speech=f"Noted bhai! {new_name} - yaad ho gaya.",
            )

        if re.match(
            r"^(?:what(?:'s| is) my name|who am i|mera naam kya hai|mujhe jaanta hai|tu mujhe jaanta)$",
            normalized,
        ):
            current_name = self._memory.user_name if (self._memory and hasattr(self._memory, "user_name")) else "Ayush"
            return Decision(
                action="none",
                speech=f"Tera naam {current_name} hai bhai - RIT Roorkee ka star aur JARVIS ka creator!",
            )

        if re.match(
            r"^(?:who made you|who created you|kisne banaya|tune kisne banaya)$",
            normalized,
        ):
            current_name = self._memory.user_name if (self._memory and hasattr(self._memory, "user_name")) else "Ayush"
            return Decision(
                action="none",
                speech=f"Mujhe {current_name} ne banaya - RIT Roorkee se, Manthan AI Hackathon 2026 ke liye. Legend hai woh.",
            )

        # Greetings
        if normalized in {
            "hello", "hi", "hey", "are you there", "wake up", "yes",
            "hi jarvis", "hello jarvis", "aye", "yo", "yo jarvis",
            "kya hal hai", "kya scene hai", "kya chal raha", "kya haal", "bhai",
        }:
            return Decision(action="none", speech=random.choice(_GREETINGS))

        if re.match(
            r"^(?:how are you|how are you doing|are you okay|you good|kaisa hai|kya haal hai|sab theek|theek ho|kaisa chal raha)$",
            normalized,
        ):
            return Decision(action="none", speech=random.choice(_HOW_ARE_YOU))

        if re.match(
            r"^(?:who are you|what is your name|your name|introduce yourself|tell me about yourself|tera naam kya hai|tu kaun hai)$",
            normalized,
        ):
            return Decision(
                action="none",
                speech=(
                    "Main hun J.A.R.V.I.S. - Just A Rather Very Intelligent System! "
                    "Ayush bhai ka personal assistant. Apps kholna, gaane bajana, baat karna - sab karta hun. Bol kya chahiye?"
                ),
            )

        if re.match(
            r"^(?:what can you do|help|what are your capabilities|commands|kya kar sakta hai|kya kuch kar sakta)$",
            normalized,
        ):
            return Decision(action="none", speech=_CAPABILITIES)

        if re.match(
            r"^(?:thank you|thanks|thank you jarvis|cheers|nice work|well done|good job|shukriya|dhanyawad|bahut acha|mast hai|badiya hai|wah yaar|zabardast)$",
            normalized,
        ):
            return Decision(action="none", speech=random.choice(_COMPLIMENTS))

        if re.match(
            r"^(?:tell me a joke|joke|say something funny|make me laugh|funny|joke suna|koi joke suna|hasao mujhe)$",
            normalized,
        ):
            return Decision(action="none", speech=random.choice(_JOKES))

        if re.match(
            r"^(?:bye|goodbye|goodnight|good night|see you|alvida|phir milenge|ok bye|tata)$",
            normalized,
        ):
            return Decision(action="none", speech="Alvida bhai! Kuch bhi chahiye toh bas bol dena. JARVIS always here.")

        if re.match(r"^(?:shut up|be quiet|stop talking|silence|chup|chup ho ja|band kar)$", normalized):
            return Decision(action="none", speech="Theek hai bhai, chup hun. Bol jab zarurat ho.")

        if re.match(r"^(?:good morning|morning|subah|subah ho gayi)$", normalized):
            return Decision(action="none", speech="Good morning bhai! Naya din, naye chances. Kya karein aaj?")

        if re.match(r"^(?:good evening|evening|good afternoon|afternoon|shaam ho gayi|shaam)$", normalized):
            return Decision(action="none", speech="Hey bhai! Shaam ho gayi - din kaisa raha? Kuch kaam baaki hai?")

        if re.match(
            r"^(?:are you real|are you human|are you an ai|are you a robot|do you have feelings|kya tu real hai|tu ai hai)$",
            normalized,
        ):
            return Decision(
                action="none",
                speech="Technically main AI hun bhai - no feelings, no food, no sleep. But conversation mein genuinely interest aata hai. So half-real? Tu decide kar.",
            )

        # Time
        if re.match(
            r"^(?:what(?:'s| is) the time|what time is it|tell me the time|current time|time now|time please|kya time hai|time batao|kitne baje hain|baj gaye kya|time kya hai|abhi kya time hai)$",
            normalized,
        ):
            now = datetime.now().strftime("%I:%M %p")
            return Decision(action="none", speech=f"Bhai, {now} baj rahe hain! Koi kaam hai?")

        # Date
        if re.match(
            r"^(?:what(?:'s| is) the date|what date is it|current date|aaj kya date hai|aaj kaun sa din hai|date batao|aaj ki date|what day is today)$",
            normalized,
        ):
            today = datetime.now().strftime("%A, %B %d, %Y")
            return Decision(action="none", speech=f"Aaj {today} hai bhai. Time flies yaar!")

        if re.match(r"^(?:what year is it|kaunsa saal hai|year kya hai)$", normalized):
            return Decision(action="none", speech=f"Bhai, {datetime.now().year} chal raha hai. Fast hai na?")

        if re.match(r"^(?:what day is it|aaj kaun sa din|din kya hai)$", normalized):
            return Decision(action="none", speech=f"Aaj {datetime.now().strftime('%A')} hai bhai!")

        # Battery
        if re.match(
            r"^(?:how(?:'s| is) (?:my )?(?:battery|power)|battery (?:status|level|percentage)|check battery|battery kitni hai|battery batao|battery check karo|battery dekho|kitni battery hai)$",
            normalized,
        ):
            return Decision(action="none", speech=self._battery_info())

        # CPU
        if re.match(
            r"^(?:(?:check )?(?:my )?(?:cpu|processor) (?:usage|load)|how(?:'s| is) (?:my )?cpu|cpu status|cpu kitna hai|cpu check karo)$",
            normalized,
        ):
            return Decision(action="none", speech=self._cpu_info())

        # RAM
        if re.match(
            r"^(?:(?:check )?(?:my )?(?:ram|memory) (?:usage|status)|how(?:'s| is) (?:my )?(?:ram|memory)|memory status|ram kitni hai|ram check karo)$",
            normalized,
        ):
            return Decision(action="none", speech=self._ram_info())

        if re.match(r"^(?:system info|system status|computer info|pc info|pc kaisa hai)$", normalized):
            return Decision(action="none", speech=self._system_info())

        if re.match(r"^(?:what(?:'s| is) my (?:ip|ip address)|my ip|ip kya hai|mera ip batao)$", normalized):
            return Decision(action="none", speech=f"Tera local IP {self._get_ip()} hai bhai.")

        # Weather
        if re.match(
            r"^(?:what(?:'s| is) the weather|weather today|weather now|how(?:'s| is) the weather|weather forecast|temperature today|weather kaisa hai|mausam kaisa hai|mausam batao|bahar kaisa hai|temperature kya hai)$",
            normalized,
        ):
            return Decision(action="none", speech=self._get_weather())

        # Volume
        if re.match(r"^(?:volume up|increase volume|turn up|louder|raise volume|volume badha|awaaz badha|zyada karo|volume badhao)$", normalized):
            return Decision(action="volume_up", speech="Volume badha raha hun bhai!")
        if re.match(r"^(?:volume down|decrease volume|turn down|softer|lower volume|quieter|volume kam karo|awaaz kam karo|volume ghata)$", normalized):
            return Decision(action="volume_down", speech="Volume kam kar raha hun.")
        if re.match(r"^(?:mute|unmute|mute (?:audio|volume)|silence|toggle mute|mute karo|band karo awaaz)$", normalized):
            return Decision(action="mute", speech="Audio mute toggle kar diya!")

        # Media
        if re.match(r"^(?:pause|resume|play pause|pause (?:music|song|video)|resume (?:music|video)|ruk ja|rok do|chalne do|play kar)$", normalized):
            return Decision(action="media_play_pause", speech="Media toggle kar diya bhai!")
        if re.match(r"^(?:next|next (?:song|track|video)|skip|skip (?:song|track)|agla gaana|next karo|skip karo)$", normalized):
            return Decision(action="media_next", speech="Next track!")
        if re.match(r"^(?:previous|previous (?:song|track)|go back|pehla gaana|back karo|previous karo)$", normalized):
            return Decision(action="media_prev", speech="Previous track!")

        # Desktop
        if re.match(r"^(?:show desktop|minimize all|go to desktop|desktop dikhao)$", normalized):
            return Decision(action="hotkey", keys=("win", "d"), speech="Desktop dikha diya!")
        if re.match(r"^(?:close (?:window|tab|this)|band karo window|window band karo)$", normalized):
            return Decision(action="hotkey", keys=("ctrl", "w"), speech="Window band kar diya!")
        if re.match(r"^(?:copy|copy (?:that|this|text|it)|copy karo)$", normalized):
            return Decision(action="hotkey", keys=("ctrl", "c"), speech="Copied bhai!")
        if re.match(r"^(?:paste|paste (?:that|this|text|it)|paste karo)$", normalized):
            return Decision(action="hotkey", keys=("ctrl", "v"), speech="Pasted!")
        if re.match(r"^(?:undo|undo (?:that|this)|undo karo|wapas karo)$", normalized):
            return Decision(action="hotkey", keys=("ctrl", "z"), speech="Undo kar diya!")

        # YouTube compound
        compound_yt = re.match(
            r"^(?:open|launch|start)\s+youtube\s+(?:and\s+)?(?:play|search(?:\s+for)?)\s+(.+?)(?:\s+(?:on|in)\s+(?:google\s+)?chrome)?$",
            normalized,
        )
        if compound_yt and compound_yt.group(1).strip():
            query = compound_yt.group(1).strip()
            in_chrome = normalized.endswith(" chrome")
            return Decision(
                action="play_youtube_in_chrome" if in_chrome else "play_youtube",
                text=query,
                speech=f"YouTube pe {query.title()} laga raha hun bhai!",
            )

        # YouTube explicit
        yt_explicit = re.match(
            r"^(?:play|search(?:\s+for)?)\s+(.+?)\s+(?:on|in)\s+youtube(?:\s+(?:on|in)\s+(?:google\s+)?chrome)?$",
            normalized,
        )
        if yt_explicit and yt_explicit.group(1).strip():
            query = yt_explicit.group(1).strip()
            in_chrome = normalized.endswith(" chrome")
            return Decision(
                action="play_youtube_in_chrome" if in_chrome else "play_youtube",
                text=query,
                speech=f"YouTube pe {query.title()} baj raha hai!",
            )

        # Hinglish YouTube: "gaana laga X", "song laga X", "bajao X"
        hinglish_yt = re.match(
            r"^(?:gaana laga|song laga|video laga|laga de|bajao|play karo|youtube pe laga)\s+(.+)$",
            normalized,
        )
        if hinglish_yt:
            query = hinglish_yt.group(1).strip()
            return Decision(action="play_youtube", text=query, speech=f"Laga raha hun - {query.title()}! Enjoy karo bhai!")

        # Play direct
        play_direct = re.match(r"^(?:play|listen to)\s+(?:song\s+)?(.+)$", normalized)
        if play_direct:
            query = play_direct.group(1).strip()
            if query not in {"music", "video", "media", "next", "previous", "something"}:
                return Decision(action="play_youtube", text=query, speech=f"{query.title()} baj raha hai!")

        # YouTube open
        youtube_in_chrome = normalized in {
            "open youtube on chrome", "open youtube in chrome",
            "launch youtube on chrome", "launch youtube in chrome",
        }
        if normalized in {"youtube", "open youtube", "launch youtube", "start youtube", "youtube khol", "youtube kholde"} or youtube_in_chrome:
            return Decision(
                action="open_url_in_chrome" if youtube_in_chrome else "open_url",
                text="https://www.youtube.com/",
                speech="YouTube aa gaya bhai!" if not youtube_in_chrome else "YouTube Chrome mein khul raha hai!",
            )

        # Web Search
        google_search = re.match(
            r"^(?:search(?:\s+(?:for|google|web))?\s+|google\s+|dhundh\s+|search karo\s+|google karo\s+)(.+?)(?:\s+on\s+(?:google|the\s+web))?$",
            normalized,
        )
        if google_search:
            query = google_search.group(1).strip()
            if len(query) > 2:
                return Decision(action="search_web", text=query, speech=f"Google pe dhundh raha hun - {query}!")

        # Math
        math_answer = self._solve_math(normalized)
        if math_answer is not None:
            return Decision(action="none", speech=f"Bhai, {math_answer}!")

        # Wikipedia
        wiki_match = re.match(
            r"^(?:who(?:\s+(?:is|was))\s+|what(?:\s+(?:is|was))\s+|tell me about\s+|explain\s+|define\s+|what is a\s+|batao\s+|bata\s+|kaun hai\s+|kya hai\s+)(.+?)\??$",
            normalized,
        )
        if wiki_match:
            query = wiki_match.group(1).strip()
            if len(query) > 1:
                answer = self._quick_wiki(query)
                if answer:
                    return Decision(action="none", speech=answer)

        # ── Typing & Dictation ───────────────────────────────────────────────
        type_match = re.match(
            r"^(?:type(?:\s+karo|\s+this)?|likho|write(?:\s+down|\s+this)?)\s+(.+)$",
            normalized,
        )
        if type_match:
            text_to_type = type_match.group(1).strip()
            return Decision(
                action="type",
                text=text_to_type,
                speech=f"Likh diya bhai: {text_to_type[:40]}",
            )

        # ── Key Presses ──────────────────────────────────────────────────────
        if re.match(r"^(?:press\s+)?enter(?:\s+dabao|\s+karo)?$", normalized):
            return Decision(action="press", key="enter", speech="Enter daba diya bhai!")
        if re.match(r"^(?:press\s+)?backspace(?:\s+dabao|\s+karo)?$", normalized):
            return Decision(action="press", key="backspace", speech="Backspace!")
        if re.match(r"^(?:press\s+)?space(?:\s+dabao|\s+bar)?$", normalized):
            return Decision(action="press", key="space", speech="Space!")
        if re.match(r"^(?:press\s+)?esc(?:ape)?(?:\s+dabao)?$", normalized):
            return Decision(action="press", key="esc", speech="Escape!")

        # ── Screenshot ───────────────────────────────────────────────────────
        if re.match(r"^(?:take\s+)?screenshot(?:\s+lo|\s+kheecho|\s+le\s+lo)?$", normalized):
            return Decision(action="hotkey", keys=("win", "prtsc"), speech="Screenshot le liya bhai!")

        # ── Screen Vision Inspection ─────────────────────────────────────────
        if re.search(r"\b(?:screen(?:\s+pe)?\s+(?:kya\s+hai|dekho|dekh|read|check)|look at (?:my )?screen|what(?:'s| is) on (?:my )?screen)\b", normalized):
            return Decision(action="none", speech="Screen analyze kar raha hun bhai - ek second!")

        # ── Big Thinking & Life Advice ────────────────────────────────────────
        if re.search(r"\b(?:kuch bada karna|bada kaise karun|life advice|career advice|kya karun main|guide karo|rasta dikhao|batao kya karun)\b", normalized):
            advice_list = [
                "Bhai, bada karne ke 3 golden rules: 1. Code daily, build real projects. 2. Network karo like-minded logon ke saath. 3. Consistency kabhi mat chhodna. Tu RIT mein hai, Hackathons jeeto, open source contribute karo. Sky is the limit!",
                "Ayush bhai, success overnight nahi aati but consistency se guarantee hoti hai. Roz 1% better bano. Project start karo, end tak le jao. Main hamesha assistance ke liye ready hun!",
                "Pehle ek skill choose karo - AI, Web3, ya Systems. Usme deep ghuso. Manthan Hackathon jaise events mein participate karte raho. Portfolio solid banao, log khud dhundhte aayenge!",
            ]
            return Decision(action="none", speech=random.choice(advice_list))

        # ── Boredom ──────────────────────────────────────────────────────────
        if re.search(r"\b(?:bore ho raha|boring lag raha|kuch interesting|kuch naya|timepass)\b", normalized):
            boredom_replies = [
                "Bore ho rahe ho? Toh chalo ek naya project idea deta hun: ek AI tool banao jo RIT ke campus notices auto-summarize kare! Ya phir Spotify pe koi fire beat lagau?",
                "Bhai boredom is the mother of creativity! Kuch naya explore karo - Python ka naya framework, ya thoda walk leke aao. Main gaana laga dun kya?",
                "Yaar bore mat ho! Main ek joke sunau, ya koi mast motivational podcast laga dun YouTube pe?",
            ]
            return Decision(action="none", speech=random.choice(boredom_replies))

        # ── Problem Sharing ──────────────────────────────────────────────────
        if re.search(r"\b(?:ek problem hai|problem share karni|baat karni hai|pareshan hun|tension ho rahi)\b", normalized):
            return Decision(
                action="none",
                speech="Bolo bhai, main sun raha hun! Academic hai ya personal? Jo bhi ho, milke sort karte hain. Tension mat lo."
            )

        # App launching
        app_name = self._opened_app_name(normalized)
        if app_name:
            alias = self._ALIASES.get(app_name)
            target = alias if alias else app_name
            return Decision(action="open_named_app", app=target, speech=f"{app_name.title()} khul raha hai bhai!")

        return None

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.lower().strip(" .,!?:;")
        value = re.sub(r"^(?:hey\s+|hi\s+|ok\s+|okay\s+)?(?:jarvis|friday)[, ]*", "", value)
        value = re.sub(r"^(?:can you\s+|could you\s+|would you\s+|please\s+)+", "", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _opened_app_name(value: str) -> Optional[str]:
        match = re.match(r"^(?:open|launch|start|run|khol|kholde|chalao|chalu karo)\s+(?:the\s+)?(.+)$", value)
        if not match:
            return None
        name = match.group(1).strip(" .,!?:;")
        if not name or any(token in name for token in ("\\", "/", ".bat", ".vbs")):
            return None
        if name.endswith(".exe"):
            name = name[:-4].strip()
        return name

    @staticmethod
    def _battery_info() -> str:
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat is None:
                return "Yaar, battery info nahi mil rahi is device pe."
            status = "charging" if bat.power_plugged else "discharging"
            mins = int(bat.secsleft / 60) if bat.secsleft > 0 and not bat.power_plugged else None
            time_str = f", roughly {mins} minutes baaki" if mins else ""
            return f"Battery {int(bat.percent)}% hai bhai - abhi {status}{time_str}."
        except Exception:
            return "Battery status nahi mil paaya yaar."

    @staticmethod
    def _cpu_info() -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            freq = psutil.cpu_freq()
            freq_str = f" at {freq.current:.0f} MHz" if freq else ""
            return f"CPU {cpu}% use ho raha hai bhai{freq_str}."
        except Exception:
            return "CPU info nahi mil paaya yaar."

    @staticmethod
    def _ram_info() -> str:
        try:
            import psutil
            mem = psutil.virtual_memory()
            used = round(mem.used / 1024 ** 3, 1)
            total = round(mem.total / 1024 ** 3, 1)
            return f"RAM {mem.percent}% use ho rahi hai bhai - {used} GB out of {total} GB."
        except Exception:
            return "RAM info nahi mil paaya yaar."

    @staticmethod
    def _system_info() -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            bat = psutil.sensors_battery()
            bat_str = f"{int(bat.percent)}% {'charging' if bat.power_plugged else 'on battery'}" if bat else "unavailable"
            return (
                f"PC ki full report bhai: CPU {cpu}%, "
                f"RAM {round(mem.used/1024**3, 1)} of {round(mem.total/1024**3, 1)} GB, battery {bat_str}."
            )
        except Exception:
            return "System info temporarily unavailable yaar."

    @staticmethod
    def _get_ip() -> str:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "unavailable"

    @staticmethod
    def _get_weather() -> str:
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast?latitude=29.87&longitude=77.9"
                "&current_weather=true&hourly=relativehumidity_2m&timezone=Asia%2FKolkata"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
            w = data["current_weather"]
            temp = w["temperature"]
            code = w.get("weathercode", 0)
            desc = {
                0: "ekdum clear sky", 1: "mostly clear", 2: "thodi clouds", 3: "overcast",
                45: "fog hai", 48: "freezing fog", 51: "halki baarish",
                61: "baarish ho rahi hai", 71: "barf pad raha",
                80: "rain showers", 95: "thunderstorm chal raha",
            }.get(code, "mixed conditions")
            return f"Roorkee mein abhi {temp} degree Celsius hai bhai - {desc}."
        except Exception:
            return "Mausam ki info nahi aa rahi yaar, net check karo."

    @staticmethod
    def _quick_wiki(query: str) -> Optional[str]:
        try:
            safe = urllib.parse.quote(query.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe}"
            req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 404:
                    return None
                data = json.loads(resp.read())
            extract = data.get("extract", "")
            if not extract:
                return None
            sentences = extract.split(". ")
            concise = ". ".join(sentences[:2]).rstrip(".") + "."
            return f"Yaar, Wikipedia ke hisaab se: {concise}"
        except Exception:
            return None

    @staticmethod
    def _solve_math(value: str) -> Optional[str]:
        prefixes = (
            "what is ", "calculate ", "solve ", "what's ", "what is the answer to ",
            "how much is ", "calculate karo ", "solve karo ", "kitna hai ",
        )
        expression = value
        for prefix in prefixes:
            if expression.startswith(prefix):
                expression = expression[len(prefix):]
                break
        replacements = {
            "multiplied by": "*", "times": "*", "plus": "+", "minus": "-",
            "divided by": "/", "over": "/", "modulo": "%", "to the power of": "**",
            "squared": "**2", "cubed": "**3",
        }
        for word, op in replacements.items():
            expression = expression.replace(word, op)
        expression = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", expression)
        expression = expression.strip(" ?=.")
        if not re.fullmatch(r"[0-9.\s+\-*/%()]{1,80}", expression) or not re.search(r"[+\-*/%]", expression):
            return None
        try:
            result = LocalIntentRouter._evaluate_arithmetic(ast.parse(expression, mode="eval").body)
        except (ArithmeticError, SyntaxError, ValueError):
            return "Yaar calculation undefined hai"
        rendered = str(int(result)) if isinstance(result, float) and result.is_integer() else str(round(result, 4))
        return f"{expression} ka answer {rendered} hai"

    @staticmethod
    def _evaluate_arithmetic(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = LocalIntentRouter._evaluate_arithmetic(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left = LocalIntentRouter._evaluate_arithmetic(node.left)
            right = LocalIntentRouter._evaluate_arithmetic(node.right)
            ops = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: (_ for _ in ()).throw(ArithmeticError("div by zero")) if b == 0 else a / b,
                ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            for op_type, func in ops.items():
                if isinstance(node.op, op_type):
                    return func(left, right)
        raise ValueError("Unsupported arithmetic")
