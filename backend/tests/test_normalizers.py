"""Tests for spoken email normalizers and dictation formatting."""
import pytest
from backend.flows.normalizers import (
    is_valid_email,
    normalize_spoken_email,
    normalize_spoken_text,
)


@pytest.mark.parametrize(
    "spoken,expected",
    [
        ("john dot smith at gmail dot com", "john.smith@gmail.com"),
        ("alice underscore 99 at the rate yahoo dot com", "alice_99@yahoo.com"),
        ("bob hyphen dev at outlook dot in", "bob-dev@outlook.in"),
        ("j o h n dot smith at gmail dot com", "john.smith@gmail.com"),
        ("send to alex at google dot com", "alex@google.com"),
        ("it is sarah dot connor at skynet dot org", "sarah.connor@skynet.org"),
        ("user dot name at proton dot me", "user.name@proton.me"),
        ("test at company dot io", "test@company.io"),
        ("dev dash ops at aws dot edu", "dev-ops@aws.edu"),
        ("admin dot root at server dot net", "admin.root@server.net"),
        ("contact at startup dot ai", "contact@startup.ai"),
        ("info at business dot co", "info@business.co"),
        ("support at service dot in", "support@service.in"),
        ("j a n e dot d o e at gmail dot com", "jane.doe@gmail.com"),
        ("david dot miller at fastmail dot com", "david.miller@fastmail.com"),
        ("hello at world dot com", "hello@world.com"),
    ],
)
def test_normalize_spoken_email(spoken, expected):
    result = normalize_spoken_email(spoken)
    assert result == expected, f"Failed for '{spoken}': got '{result}' expected '{expected}'"
    assert is_valid_email(result), f"Result '{result}' should be a valid email"


@pytest.mark.parametrize(
    "invalid",
    [
        "not an email address",
        "johnsmith",
        "@gmail.com",
        "john@",
        "hello at nowhere",
        "",
    ],
)
def test_invalid_email_detection(invalid):
    cleaned = normalize_spoken_email(invalid)
    assert not is_valid_email(cleaned), f"'{invalid}' -> '{cleaned}' should NOT be valid"


def test_normalize_spoken_text():
    raw = "hello comma world full stop this is line one newline this is line two period"
    expected = "Hello, world. This is line one\nThis is line two."
    result = normalize_spoken_text(raw)
    assert result == expected

    question = "how are you question mark i am doing fine exclamation point"
    expected_q = "How are you? I am doing fine!"
    assert normalize_spoken_text(question) == expected_q
