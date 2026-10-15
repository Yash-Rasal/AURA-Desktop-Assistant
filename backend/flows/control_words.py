"""Control word detection using regex and fuzzy string matching."""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional, Tuple, List
from rapidfuzz import fuzz

try:
    from commands.dispatcher import _strip_conversational_fillers
except ImportError:
    from backend.commands.dispatcher import _strip_conversational_fillers


class ControlWord(str, Enum):
    DONE = "DONE"
    NEXT = "NEXT"
    SKIP = "SKIP"
    BACK = "BACK"
    CANCEL = "CANCEL"
    SEND = "SEND"
    YES = "YES"
    NO = "NO"
    REPEAT = "REPEAT"


# Canonical phrase targets for fuzzy comparison
_CONTROL_PHRASES: List[Tuple[ControlWord, List[str]]] = [
    (
        ControlWord.DONE,
        [
            "done", "ok done", "okay done", "completed", "finished", "that's all",
            "thats all", "that is all", "that's it", "thats it", "all done",
            "i am done", "i'm done", "im done", "finish", "complete", "all finished",
            "yeah that's all", "yeah thats all", "yes that's all", "yeah that is all",
        ],
    ),
    (
        ControlWord.NEXT,
        [
            "next", "continue", "move on", "proceed", "go next", "next step", "next field"
        ],
    ),
    (
        ControlWord.SKIP,
        [
            "skip", "leave blank", "pass", "skip this", "skip step", "skip it", "no need"
        ],
    ),
    (
        ControlWord.BACK,
        [
            "back", "go back", "previous", "previous step", "previous one",
            "take me back", "step back", "undo", "last step"
        ],
    ),
    (
        ControlWord.CANCEL,
        [
            "cancel", "stop", "never mind", "nevermind", "abort", "quit", "exit",
            "cancel flow", "forget it", "please stop", "cancel that", "drop it",
            "discard", "stop flow"
        ],
    ),
    (
        ControlWord.SEND,
        [
            "send", "send it", "open draft", "open email", "compose", "send email",
            "draft it", "ready to send", "review draft"
        ],
    ),
    (
        ControlWord.YES,
        [
            "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "looks good",
            "correct", "do it", "go ahead", "sounds good", "perfect", "yup", "aye"
        ],
    ),
    (
        ControlWord.NO,
        [
            "no", "nope", "wait", "not yet", "don't send", "dont send", "hold on",
            "stop wait", "not good", "wrong", "change it"
        ],
    ),
    (
        ControlWord.REPEAT,
        [
            "repeat", "say again", "what did you say", "pardon", "repeat that",
            "what was that", "say that again", "one more time", "pardon me"
        ],
    ),
]

# Explicit regexes for fast matching
_EXACT_REGEX = {
    ControlWord.CANCEL: re.compile(r"^(?:cancel(?:\s+(?:flow|that|it))?|never\s*mind|abort|forget\s+it|please\s+stop|discard|stop\s+flow)$", re.IGNORECASE),
    ControlWord.BACK: re.compile(r"^(?:go\s+back|back(?:\s+up)?|previous(?:\s+(?:step|one))?|undo)$", re.IGNORECASE),
    ControlWord.SKIP: re.compile(r"^(?:skip(?:\s+(?:this|it|step))?|leave\s+blank|pass)$", re.IGNORECASE),
    ControlWord.DONE: re.compile(r"^(?:(?:yeah|yes|yep|ok|okay|all|i am|i'm)?\s*(?:done|completed|finished)|(?:yeah|yes|yep|ok|okay)?\s*that(?:'s|\s+is)\s+(?:all|it)|all\s+set)$", re.IGNORECASE),
    ControlWord.NEXT: re.compile(r"^(?:next(?:\s+(?:step|field))?|continue|proceed|move\s+on)$", re.IGNORECASE),
    ControlWord.SEND: re.compile(r"^(?:send(?:\s+(?:it|email))?|open\s+(?:the\s+)?draft|review\s+draft)$", re.IGNORECASE),
    ControlWord.YES: re.compile(r"^(?:yes|yeah|yep|yup|sure|ok|okay|confirm|looks\s+good|correct|do\s+it|go\s+ahead|sounds\s+good|perfect)$", re.IGNORECASE),
    ControlWord.NO: re.compile(r"^(?:no|nope|wait|not\s+yet|don\'?t\s+send|hold\s+on|change\s+it)$", re.IGNORECASE),
    ControlWord.REPEAT: re.compile(r"^(?:repeat(?:\s+that)?|say\s+(?:that\s+)?again|what\s+did\s+you\s+say|pardon(?:\s+me)?|one\s+more\s+time)$", re.IGNORECASE),
}


def detect_control_word(text: str) -> Optional[ControlWord]:
    """
    Detect whether the user input matches a recognized flow control word.
    Handles conversational fillers and punctuation, followed by regex & fuzzy matching.
    Returns None if text does not closely match a control word.
    """
    if not text:
        return None

    clean = _strip_conversational_fillers(text).lower().strip(" \t\r\n.?!,;:\"'`")
    if not clean:
        return None

    # Guard: Long sentences (> 6 words) are almost certainly slot content (e.g. subject or body)
    # unless it explicitly starts with 'cancel' or 'never mind'
    words = clean.split()
    if len(words) > 6:
        if clean.startswith("cancel") or clean.startswith("never mind"):
            return ControlWord.CANCEL
        return None

    # 1. Exact regex matches
    for cw, regex in _EXACT_REGEX.items():
        if regex.match(clean):
            return cw

    # 2. Fuzzy matching against control phrases
    best_cw: Optional[ControlWord] = None
    best_score: float = 0.0

    for cw, phrases in _CONTROL_PHRASES:
        for phrase in phrases:
            # Score against ratio and partial ratio
            score = fuzz.ratio(clean, phrase)
            if score > best_score:
                best_score = score
                best_cw = cw

    # Threshold: >= 86 for short fuzzy matches
    if best_score >= 86.0 and best_cw is not None:
        # Extra safety check for short opposites ("no" vs "go", "yes")
        if best_cw in (ControlWord.YES, ControlWord.NO) and len(clean) <= 3 and best_score < 95.0:
            return None
        return best_cw

    return None
