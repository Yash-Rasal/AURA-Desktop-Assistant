"""Normalizers for spoken speech input (emails, punctuation, text formatting)."""
from __future__ import annotations

import re


_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


def normalize_spoken_email(raw_text: str) -> str:
    """
    Convert spoken email phrases into a clean email address.
    Example:
        'john dot smith at gmail dot com' -> 'john.smith@gmail.com'
        'alice underscore 99 at the rate yahoo dot com' -> 'alice_99@yahoo.com'
        'bob hyphen dev at outlook dot in' -> 'bob-dev@outlook.in'
    """
    if not raw_text:
        return ""

    text = raw_text.strip().lower()

    # If it is enclosed in quotes or mailto:, strip them
    text = re.sub(r"^mailto:\s*", "", text)
    text = text.strip("\"'<>[]()")

    # Handle common prefixes like "send to", "to", "it is", "email is"
    text = re.sub(r"^(?:send\s+to|to|my\s+email\s+is|it\s+is|email\s+is)\s+", "", text, flags=re.IGNORECASE)

    # 1. Spoken symbols
    text = re.sub(r"\bat\s+the\s+rate(?:\s+of)?\b", "@", text)
    text = re.sub(r"\bat\b", "@", text)

    text = re.sub(r"\bdot\b", ".", text)
    text = re.sub(r"\bunderscore\b", "_", text)
    text = re.sub(r"\b(?:dash|hyphen|minus)\b", "-", text)

    # 2. Fix TLDs if spaced
    tlds = ["com", "in", "org", "net", "edu", "gov", "io", "co", "ai", "me", "info", "dev"]
    for tld in tlds:
        text = re.sub(rf"\.\s*{tld}\b", f".{tld}", text)

    # 3. Collapse spaces between single letters (e.g., "j o h n" -> "john")
    # Repeatedly combine single character sequences separated by single space
    # Example: "j o h n . s m i t h @ g m a i l . c o m"
    tokens = text.split()
    joined_tokens = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        # If token is a single char or symbol
        if len(token) == 1 and token not in ("@", ".", "_", "-"):
            # Gather consecutive single letters
            sub = [token]
            while i + 1 < len(tokens) and len(tokens[i + 1]) == 1 and tokens[i + 1] not in ("@", ".", "_", "-"):
                i += 1
                sub.append(tokens[i])
            joined_tokens.append("".join(sub))
        else:
            joined_tokens.append(token)
        i += 1

    text = "".join(joined_tokens)

    # Remove all remaining whitespace
    text = re.sub(r"\s+", "", text)

    # Handle double dots or trailing dots
    text = re.sub(r"\.{2,}", ".", text)
    text = text.strip(".")

    return text


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email or "@" not in email:
        return False
    return bool(_EMAIL_REGEX.match(email.strip()))


def normalize_spoken_text(text: str) -> str:
    """
    Format spoken text into natural written text:
    - Replaces spoken punctuation words ('comma', 'full stop', 'period', 'new line', etc.)
    - Formats spacing around punctuation
    - Capitalizes sentences properly
    """
    if not text:
        return ""

    s = text.strip()

    # Spoken punctuation replacements
    replacements = [
        (r"\b(?:new\s+paragraph)\b", "\n\n"),
        (r"\b(?:new\s+line|newline)\b", "\n"),
        (r"\b(?:full\s+stop|period)\b", "."),
        (r"\b(?:comma)\b", ","),
        (r"\b(?:question\s+mark)\b", "?"),
        (r"\b(?:exclamation\s+mark|exclamation\s+point)\b", "!"),
        (r"\b(?:colon)\b", ":"),
        (r"\b(?:semicolon|semi\s+colon)\b", ";"),
    ]

    for pat, rep in replacements:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)

    # Clean spacing before punctuation marks (e.g. "hello , world" -> "hello, world")
    s = re.sub(r"\s+([,\.\?!:;])", r"\1", s)
    # Ensure a single space after punctuation (unless newline)
    s = re.sub(r"([,\.\?!:;])(?=[^\s\n\d])", r"\1 ", s)

    # Clean redundant whitespace (preserve double newlines for paragraphs)
    lines = s.split("\n")
    cleaned_lines = []
    for line in lines:
        line_clean = re.sub(r"[ \t]+", " ", line).strip()
        if not line_clean:
            cleaned_lines.append("")
            continue

        # Capitalize start of sentence in this line
        # Split sentences by period/exclamation/question mark
        parts = re.split(r"([\.\?!]\s*)", line_clean)
        capitalized_parts = []
        for p in parts:
            if p and p[0].isalpha():
                capitalized_parts.append(p[0].upper() + p[1:])
            else:
                capitalized_parts.append(p)
        cleaned_lines.append("".join(capitalized_parts))

    result = "\n".join(cleaned_lines)
    return result.strip()
