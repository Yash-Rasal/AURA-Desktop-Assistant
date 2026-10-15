"""Email guided conversational flow with Gmail Web, Mailto, and Outlook Desktop providers."""
from __future__ import annotations

import asyncio
import logging
import os
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Tuple

try:
    from config import settings
    from flows.engine import BaseFlow, FlowStep, register_flow
    from flows.normalizers import (
        is_valid_email,
        normalize_spoken_email,
        normalize_spoken_text,
    )
except ImportError:
    from backend.config import settings
    from backend.flows.engine import BaseFlow, FlowStep, register_flow
    from backend.flows.normalizers import (
        is_valid_email,
        normalize_spoken_email,
        normalize_spoken_text,
    )

logger = logging.getLogger("flows.email")


def _mask_email(email: str) -> str:
    """Mask email address for privacy-safe logging (e.g. j***@gmail.com)."""
    if not email or "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    masked_user = (user[0] + "***") if len(user) > 0 else "***"
    return f"{masked_user}@{domain}"


def _validate_recipient(text: str, _slots: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate and normalize recipient email address."""
    clean = normalize_spoken_email(text)
    if not clean:
        return False, None, "Please provide the recipient's email address."

    if not is_valid_email(clean):
        return False, None, f"'{clean}' doesn't look like a valid email address. Please say it again or say it letter-by-letter."

    return True, clean, None


def _validate_subject(text: str, _slots: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate and normalize subject line."""
    norm = normalize_spoken_text(text)
    if not norm:
        return False, None, "Please provide a subject line."
    return True, norm, None


def _open_gmail_web(to: str, subject: str, body: str) -> bool:
    """Open Gmail compose window in default browser."""
    query = urllib.parse.urlencode({
        "view": "cm",
        "fs": "1",
        "to": to,
        "su": subject,
        "body": body,
    })
    url = f"https://mail.google.com/mail/?{query}"
    return webbrowser.open(url)


def _open_mailto(to: str, subject: str, body: str) -> bool:
    """Open default mail client via mailto: URL."""
    query = urllib.parse.urlencode({
        "subject": subject,
        "body": body,
    })
    mailto_url = f"mailto:{to}?{query}"
    try:
        # On Windows, os.startfile is the cleanest for mailto:
        if hasattr(os, "startfile"):
            os.startfile(mailto_url)
            return True
    except Exception as e:
        logger.warning("os.startfile mailto failed: %s", e)

    return webbrowser.open(mailto_url)


def _open_outlook_desktop(to: str, subject: str, body: str) -> bool:
    """Open Outlook desktop application via COM automation."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        mail.Display()
        return True
    except Exception as e:
        logger.warning("Outlook COM failed: %s; falling back to mailto", e)
        return _open_mailto(to, subject, body)


def _live_typing_mode(to: str, subject: str, body: str) -> None:
    """
    Simulate pasting content into active compose window.
    FRAGILITY WARNING:
    This mode relies on simulated keyboard inputs (Ctrl+V, Tab) and clipboard manipulation.
    Timing varies widely based on browser responsiveness, network latency, and desktop focus.
    If focus is lost, keys may be sent to arbitrary active windows. pyautogui.FAILSAFE is
    enabled (slam mouse into any screen corner to abort).
    """
    try:
        import time
        import pyautogui
        import pyperclip

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.3

        time.sleep(2.0)  # Allow compose window to load/focus

        # Paste recipient
        pyperclip.copy(to)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.4)
        pyautogui.press("tab")

        # Paste subject
        pyperclip.copy(subject)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.4)
        pyautogui.press("tab")

        # Paste body
        pyperclip.copy(body)
        pyautogui.hotkey("ctrl", "v")
    except Exception as e:
        logger.error("Live typing error: %s", e)


@register_flow
class EmailFlow(BaseFlow):
    name: str = "email"
    title: str = "Compose Email"

    steps = [
        FlowStep(
            slot_name="to",
            prompt="Who would you like to send this email to?",
            focus_field="recipient",
            validator=_validate_recipient,
        ),
        FlowStep(
            slot_name="subject",
            prompt="What is the subject of the email?",
            focus_field="subject",
            validator=_validate_subject,
        ),
        FlowStep(
            slot_name="body",
            prompt="What would you like to say in the body? Say 'done' when you are finished.",
            focus_field="body",
            multiline=True,
        ),
    ]

    def format_confirm_prompt(self, slots: Dict[str, Any]) -> str:
        to_addr = slots.get("to", "")
        subj = slots.get("subject", "No Subject")
        return f"Your email to {to_addr} with subject '{subj}' is ready. Would you like me to open the draft? Say 'yes' or 'send'."

    async def execute(self, slots: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Execute email draft opening.
        SAFETY RULE:
        Never auto-send emails or messages. Always open the compose window prefilled
        and prompt the user to review and send it themselves.
        """
        to_addr = slots.get("to", "").strip()
        subject = slots.get("subject", "").strip()
        body = slots.get("body", "").strip()

        logger.info("Executing email flow for recipient=%s (body hidden for privacy)", _mask_email(to_addr))

        provider = getattr(settings, "email_provider", "gmail_web").lower()
        live_typing = getattr(settings, "email_live_typing", False)

        success = False
        try:
            if provider == "outlook_com":
                success = await asyncio.to_thread(_open_outlook_desktop, to_addr, subject, body)
            elif provider == "mailto":
                success = await asyncio.to_thread(_open_mailto, to_addr, subject, body)
            else:  # default to gmail_web
                success = await asyncio.to_thread(_open_gmail_web, to_addr, subject, body)

            if live_typing and success:
                asyncio.create_task(asyncio.to_thread(_live_typing_mode, to_addr, subject, body))

        except Exception as e:
            logger.exception("Failed to open email draft: %s", e)
            return False, f"Could not open your email client: {e}. Please check your default email settings.", None

        reply = "Your draft is ready. Review and send it yourself."
        card_data = {
            "type": "email_draft_ready",
            "provider": provider,
            "to": to_addr,
            "subject": subject,
            "slots": slots,
            "reply": reply,
        }
        return True, reply, card_data
