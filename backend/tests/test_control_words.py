"""Tests for control word detection and fuzzy matching."""
import pytest
from backend.flows.control_words import ControlWord, detect_control_word


@pytest.mark.parametrize(
    "phrase,expected",
    [
        # DONE
        ("done", ControlWord.DONE),
        ("ok done", ControlWord.DONE),
        ("okay done", ControlWord.DONE),
        ("completed", ControlWord.DONE),
        ("finished", ControlWord.DONE),
        ("yeah that's all", ControlWord.DONE),
        ("thats all", ControlWord.DONE),
        ("that is all", ControlWord.DONE),
        ("that's it", ControlWord.DONE),
        ("all done", ControlWord.DONE),
        ("i am done", ControlWord.DONE),
        ("i'm done", ControlWord.DONE),
        # CANCEL
        ("cancel", ControlWord.CANCEL),
        ("please stop", ControlWord.CANCEL),
        ("never mind", ControlWord.CANCEL),
        ("nevermind", ControlWord.CANCEL),
        ("hey jarvis cancel", ControlWord.CANCEL),
        ("abort", ControlWord.CANCEL),
        ("quit", ControlWord.CANCEL),
        ("cancel flow", ControlWord.CANCEL),
        ("forget it", ControlWord.CANCEL),
        ("discard", ControlWord.CANCEL),
        # BACK
        ("back", ControlWord.BACK),
        ("go back", ControlWord.BACK),
        ("previous", ControlWord.BACK),
        ("previous step", ControlWord.BACK),
        ("previous one", ControlWord.BACK),
        ("take me back", ControlWord.BACK),
        ("undo", ControlWord.BACK),
        # SKIP
        ("skip", ControlWord.SKIP),
        ("leave blank", ControlWord.SKIP),
        ("pass", ControlWord.SKIP),
        ("skip this", ControlWord.SKIP),
        # NEXT
        ("next", ControlWord.NEXT),
        ("continue", ControlWord.NEXT),
        ("move on", ControlWord.NEXT),
        ("proceed", ControlWord.NEXT),
        # SEND
        ("send", ControlWord.SEND),
        ("send it", ControlWord.SEND),
        ("open draft", ControlWord.SEND),
        ("review draft", ControlWord.SEND),
        # YES
        ("yes", ControlWord.YES),
        ("yeah", ControlWord.YES),
        ("yep", ControlWord.YES),
        ("sure", ControlWord.YES),
        ("confirm", ControlWord.YES),
        ("looks good", ControlWord.YES),
        ("correct", ControlWord.YES),
        ("do it", ControlWord.YES),
        # NO
        ("no", ControlWord.NO),
        ("nope", ControlWord.NO),
        ("wait", ControlWord.NO),
        ("not yet", ControlWord.NO),
        ("don't send", ControlWord.NO),
        ("hold on", ControlWord.NO),
        # REPEAT
        ("repeat", ControlWord.REPEAT),
        ("say again", ControlWord.REPEAT),
        ("what did you say", ControlWord.REPEAT),
        ("pardon", ControlWord.REPEAT),
    ],
)
def test_control_words_recognized(phrase, expected):
    res = detect_control_word(phrase)
    assert res == expected, f"Expected '{phrase}' to match {expected}, got {res}"


@pytest.mark.parametrize(
    "phrase",
    [
        "The dog was not done eating dinner tonight",
        "Hello jarvis how are you doing today?",
        "Please write a function in python",
        "john.smith@gmail.com",
        "Meeting agenda for tomorrow morning at 10am",
    ],
)
def test_non_control_words_ignored(phrase):
    res = detect_control_word(phrase)
    assert res is None, f"Expected '{phrase}' to return None, got {res}"
