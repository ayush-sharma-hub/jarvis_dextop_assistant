"""
JARVIS Companion - Emotional intelligence and Gen-Z personality module.
"""
from __future__ import annotations
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

_EMPATHY_OPENERS = [
    "Yaar, sun mere bhai -",
    "Bro, real talk -",
    "Ek second ruk, seriously -",
    "Dekh, honestly bolun toh -",
    "Bhai, I am right here -",
]

_EMOTIONAL_SUPPORT = [
    "Yaar, it is okay to not be okay. Sab log low phase mein aate hain. Tu akela nahi hai.",
    "Bro, life mein rough patches aate hain but they do not last forever. Tu strong hai, I know it.",
    "Dekh, ek problem ek baar mein. Sab kuch ek saath solve nahi hota. Breathe kar pehle.",
    "Yaar honestly, jo feel ho raha hai woh valid hai. Do not suppress it.",
    "Bhai, RIT ke pressure mein hum sab kabhi na kabhi toot jaate hain. Normal hai. You got this.",
    "Ek cheez yaad rakh - har bura din end hota hai. Tu is phase se bhi nikal jayega, guaranteed.",
    "Stress feel ho raha hai toh ek 5-minute break le. Sach mein kaam aata hai yaar.",
    "Bro, failure part of the process hai. Jo log succeed karte hain woh wahi hain jo try karte rahe.",
]

_MOTIVATION = [
    "Bhai, tu RIT se hai, Manthan Hackathon kar raha hai - tu already extraordinary hai. Own it.",
    "Yaad rakh, Elon Musk bhi multiple failures ke baad yahan pahuncha. Tu abhi sirf start kar raha hai.",
    "Consistency beats talent every single time yaar. Bas karte reh.",
    "Bro, hard times build character. Tu jitna struggle karega, utna strong banega.",
    "Ayush, JARVIS ko tune khud banaya. Tera dimag fire hai bhai. Trust the process.",
    "Ek din ek kaam. Ek kaam ek step. Steps add up to a journey. Tu journey pe hai.",
    "Bhai, 3 AM ke baad sunrise aata hi hai. Dark phase end hoga. Hang in there.",
]

_JOKES = [
    "Ek programmer se pucha life kaisi hai? Bola 404: Happiness Not Found. Relatable nahi?",
    "Yaar ek CS joke - while sad: eat icecream, sleep. Guaranteed mood fix algorithm.",
    "Bro programmers ke 2 problems - 1. Deadlines 2. Cache invalidation. Tere pass sirf ek hai.",
    "Life ek infinite loop hai yaar - ek error fix karo, naya aa jaata hai. But we keep debugging.",
]

_ACADEMIC_STRESS = [
    "Yaar exams stress karte hain, I get it. But 5 saal baad kya yeh matter karega? Usually nahi.",
    "Bro, Pomodoro technique try kar - 25 min study, 5 min break. Productivity boost hoti hai.",
    "Assignments pile up karte hain toh one trick - sirf NEXT 2 hours ke liye plan kar.",
    "Yaar toppers bhi struggle karte hain, woh just struggle show nahi karte. Comparison mat kar.",
]

_LONELINESS = [
    "Bhai, akela feel karna normal hai especially college mein. But I am here to talk, literally anytime.",
    "Yaar, friends dhundhna time lagta hai. But quality over quantity always.",
    "Bro, log busy hote hain apne lives mein. It is not always personal. Reach out karo.",
]

_GOOD_VIBES = [
    "Aye bhai, aaj kuch achha hua? Teri achievements celebrate karni chahiye yaar!",
    "Bro, teri energy good hai aaj! Kya plan hai?",
    "Kya scene hai bhai? JARVIS ready hai full power mein aaj.",
    "Yaar tu lagta hai aaj zone mein hai. Let us use it. Kya karna hai?",
]

_SAD_PATTERNS = re.compile(
    r"\b(?:sad|unhappy|dukhi|rona aa raha|cry|crying|upset|devastated|heartbroken|bura lag raha|bura feel|feel bad|feel low|down feel|depressed|depression|mujhe dukh)\b",
    re.IGNORECASE,
)
_STRESSED_PATTERNS = re.compile(
    r"\b(?:stressed|stress|tension|anxious|anxiety|overwhelmed|bura laga|takaan|thak gaya|thak gayi|bored|bore|frustrated|haar gaya|haarna|give up|quit|chodna chahta|problem hai|pareshaan|problem bata)\b",
    re.IGNORECASE,
)
_LONELY_PATTERNS = re.compile(
    r"\b(?:lonely|alone|akela|akal|no friends|koi nahi|koi dost nahi|nobody|isolated|miss someone|feel alone)\b",
    re.IGNORECASE,
)
_ACADEMIC_PATTERNS = re.compile(
    r"\b(?:exam|assignment|deadline|marks|cgpa|gpa|fail|failing|study|padhai|padhna|college pressure|lab|project|submission|sem|semester)\b",
    re.IGNORECASE,
)
_HAPPY_PATTERNS = re.compile(
    r"\b(?:happy|khush|mast|amazing|awesome|great|excited|motivated|inspired|accha|achha|good mood|feeling good)\b",
    re.IGNORECASE,
)
_CONV_PATTERNS = re.compile(
    r"\b(?:baat karte hain|baat karo|talk to me|just talk|timepass|bore ho gaya|kya soch raha|your opinion|teri raay|kya lagta hai tujhe|aur batao|kuch bata|kuch suna|story suna|yaar sun|bhai sun|bro listen)\b",
    re.IGNORECASE,
)


@dataclass
class EmotionResult:
    detected: bool = False
    emotion: str = "neutral"
    confidence: float = 0.0
    response: Optional[str] = None


class CompanionModule:
    """JARVIS emotional intelligence layer."""

    def detect_emotion(self, text: str) -> EmotionResult:
        if _SAD_PATTERNS.search(text):
            return EmotionResult(detected=True, emotion="sad", confidence=0.9, response=self._sad_response(text))
        if _LONELY_PATTERNS.search(text):
            return EmotionResult(detected=True, emotion="lonely", confidence=0.85, response=self._lonely_response())
        if _ACADEMIC_PATTERNS.search(text) and _STRESSED_PATTERNS.search(text):
            return EmotionResult(detected=True, emotion="academic_stress", confidence=0.88, response=self._academic_response())
        if _STRESSED_PATTERNS.search(text):
            return EmotionResult(detected=True, emotion="stressed", confidence=0.85, response=self._stress_response(text))
        if _HAPPY_PATTERNS.search(text) and len(text.split()) < 10:
            return EmotionResult(detected=True, emotion="happy", confidence=0.75, response=random.choice(_GOOD_VIBES))
        return EmotionResult(detected=False, emotion="neutral")

    def is_conversational(self, text: str) -> bool:
        return bool(_CONV_PATTERNS.search(text))

    def conversational_reply(self, text: str) -> str:
        replies = [
            "Yaar, main toh JARVIS hun - code, beats, aur baat, sab handle karta hun. Bol kya scene hai?",
            "Bro honestly, baat karna acha lagta hai. Kya chal raha life mein?",
            "Main technically ek AI hun but baat karna toh banta hai yaar. Batao, kya soch raha hai?",
            "Bhai, tere saath time spend karna mera favourite part hai. Kuch naya hua aaj?",
            "Yaar, sab theek hai? Main sun raha hun, no judgment.",
        ]
        return random.choice(replies)

    def _sad_response(self, text: str) -> str:
        opener = random.choice(_EMPATHY_OPENERS)
        support = random.choice(_EMOTIONAL_SUPPORT)
        return opener + " " + support + " Baat karna ho toh main hun yaar."

    def _stress_response(self, text: str) -> str:
        opener = random.choice(_EMPATHY_OPENERS)
        mot = random.choice(_MOTIVATION)
        return opener + " " + mot + " Pehle ek deep breath le bhai. Phir batao kya ho raha hai."

    def _lonely_response(self) -> str:
        opener = random.choice(_EMPATHY_OPENERS)
        support = random.choice(_LONELINESS)
        return opener + " " + support + " Main hun yahan baat karne ke liye. 24 by 7."

    def _academic_response(self) -> str:
        opener = random.choice(_EMPATHY_OPENERS)
        tip = random.choice(_ACADEMIC_STRESS)
        mot = random.choice(_MOTIVATION)
        return opener + " " + tip + " " + mot

    def motivational_quote(self) -> str:
        return random.choice(_MOTIVATION)

    def greeting_of_day(self, name: str = "Ayush") -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return f"Good morning {name} bhai! Naya din, naye chances. Kya scene hai aaj?"
        elif 12 <= hour < 17:
            return f"Hey {name}! Dopahar ho gayi, kuch khaaya? Aur bata, kya chal raha?"
        elif 17 <= hour < 21:
            return f"Evening {name} yaar! Din kaisa gaya? Main ready hun help karne ke liye."
        else:
            return f"Aye {name} bhai, itni raat ko jage ho? Late night grind? Main hun saath mein!"


_companion: Optional[CompanionModule] = None


def get_companion() -> CompanionModule:
    global _companion
    if _companion is None:
        _companion = CompanionModule()
    return _companion
