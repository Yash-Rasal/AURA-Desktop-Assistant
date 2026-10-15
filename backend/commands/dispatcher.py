from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .apps import launch_app
from .web import launch_website, resolve_web_target
from .hardware import (
    adjust_volume,
    set_volume,
    set_mute,
    get_volume_status,
    adjust_brightness,
    set_brightness,
    get_brightness_status,
)
from .power import (
    lock_workstation,
    sleep_computer,
    shutdown_computer,
    restart_computer,
    cancel_shutdown,
)

# File extensions to ignore so we don't intercept file operations
FILE_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls", ".pptx", ".ppt",
    ".zip", ".rar", ".7z", ".png", ".jpg", ".jpeg", ".mp3", ".wav", ".mp4",
    ".py", ".js", ".ts", ".html", ".css", ".json", ".md",
}


def _strip_conversational_fillers(text: str) -> str:
    """Strip greetings, polite filler words, and punctuation."""
    norm = text.strip()
    norm = re.sub(r"^(?:alright|okay|ok|hey|hi|hello)?\s*(?:sir|jarvis|assistant|computer)?[\s,:\-]*", "", norm, flags=re.IGNORECASE).strip()
    norm = re.sub(r"^(?:can\s+you|could\s+you|please|would\s+you|i\s+want\s+to|help\s+me\s+to|go\s+ahead\s+and)?\s*(?:please)?[\s,:\-]*", "", norm, flags=re.IGNORECASE).strip()
    norm = re.sub(r"[\s,:\-]+(?:please|for\s+me|right\s+now|now|immediately)[\.\?!]*$", "", norm, flags=re.IGNORECASE).strip()
    return norm.strip(" \t\r\n.?!,;:\"'`")


def _safe_save_context(app: str = "", last_action: str = "", last_query: str = "", last_url: str = "") -> None:
    """Safely record desktop context for follow-up actions without failing."""
    try:
        from backend.flows.context_followups import save_context
        save_context(app=app, last_action=last_action, last_query=last_query, last_url=last_url)
    except Exception:
        pass


async def handle_quick_command(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Evaluate user message against Quick Commands:
    - Lock / Shut Down / Restart / Sleep / Cancel
    - Volume Up / Down / Set / Mute / Unmute
    - Brightness Up / Down / Set
    - Launch Websites & Web Search
    - Open Applications
    Returns a result dict if handled, or None if regular LLM/file intent.
    """
    clean = _strip_conversational_fillers(raw_text)
    if not clean:
        return None

    lower = clean.lower()

    # Never intercept general questions
    if re.match(r"^(what\s+is|what\'s|how\s+to|how\s+do|why\s+is|why\s+do|tell\s+me\s+about|explain)\b", lower):
        # Exception: "what is the volume", "what is the brightness"
        if not re.search(r"\b(volume|brightness|sound)\b", lower):
            return None

    # Never intercept screen vision commands
    if re.search(r"\b(on\s+(?:the\s+|my\s+)?screen|at\s+(?:the\s+|my\s+)?screen|look\s+at\s+(?:the\s+|my\s+)?screen)\b", lower):
        return None

    # ---------------------------------------------------------
    # 1. POWER COMMANDS
    # ---------------------------------------------------------
    # Cancel shutdown
    if re.search(r"\b(cancel|abort|stop)\s+(?:the\s+)?(?:shutdown|shut\s*down|restart|reboot)\b", lower):
        res = cancel_shutdown()
        return {"action": "cancel_shutdown", "category": "power", "data": res, "reply": res["reply"]}

    # Lock workstation
    if re.search(r"\b(?:lock|lock\s+up)\s+(?:the\s+|my\s+)?(?:pc|computer|screen|workstation|windows|laptop)\b", lower) or lower in ["lock pc", "lock screen", "lock computer", "lock workstation"]:
        res = lock_workstation()
        return {"action": "lock", "category": "power", "data": res, "reply": res["reply"]}

    # Sleep
    if re.search(r"\b(?:put\s+(?:the\s+|my\s+)?(?:pc|computer|laptop)\s+to\s+sleep|sleep\s+(?:the\s+|my\s+)?(?:pc|computer|laptop))\b", lower) or lower in ["sleep pc", "sleep computer", "put pc to sleep"]:
        res = sleep_computer()
        return {"action": "sleep", "category": "power", "data": res, "reply": res["reply"]}

    # Shut down
    if re.search(r"\b(?:shut\s*down|turn\s+off|power\s+off)\s+(?:the\s+|my\s+)?(?:pc|computer|laptop|system|machine)?\b", lower) or lower in ["shutdown", "shut down"]:
        res = shutdown_computer(delay_seconds=20)
        return {"action": "shutdown", "category": "power", "data": res, "reply": res["reply"]}

    # Restart / Reboot
    if re.search(r"\b(?:restart|reboot)\s+(?:the\s+|my\s+)?(?:pc|computer|laptop|system|machine)?\b", lower) or lower in ["restart", "reboot"]:
        res = restart_computer(delay_seconds=15)
        return {"action": "restart", "category": "power", "data": res, "reply": res["reply"]}

    # ---------------------------------------------------------
    # 2. HARDWARE: VOLUME
    # ---------------------------------------------------------
    # Mute / Unmute
    if re.search(r"\b(?:mute\s+(?:the\s+)?(?:audio|sound|volume)|mute)\b", lower) and not re.search(r"\bunmute\b", lower):
        res = set_mute(True)
        return {"action": "volume_mute", "category": "hardware", "data": res, "reply": res["reply"]}

    if re.search(r"\b(?:unmute\s+(?:the\s+)?(?:audio|sound|volume)|unmute)\b", lower):
        res = set_mute(False)
        return {"action": "volume_unmute", "category": "hardware", "data": res, "reply": res["reply"]}

    # Check volume
    if re.search(r"\b(?:what(?:\'s|\s+is)\s+(?:the\s+)?volume|check\s+volume|current\s+volume)\b", lower):
        status = get_volume_status()
        reply = f"Current volume is {status.get('percent', 0)}%." + (" (Muted)" if status.get("muted") else "")
        return {"action": "volume_status", "category": "hardware", "data": status, "reply": reply}

    # Volume Set (e.g. "set volume to 60%", "volume to 70", "volume 50%")
    vol_set = re.search(r"\b(?:set\s+(?:the\s+)?volume\s+(?:to\s+)?|change\s+volume\s+to\s+|volume\s+(?:to\s+)?)([0-9]{1,3})\s*(?:%|percent)?\b", lower)
    if vol_set:
        pct = int(vol_set.group(1))
        res = set_volume(pct)
        return {"action": "volume_set", "category": "hardware", "data": res, "reply": res["reply"]}

    # Volume Up
    if re.search(r"\b(?:volume\s+up|increase\s+(?:the\s+)?volume|raise\s+(?:the\s+)?volume|turn\s+up\s+(?:the\s+)?volume|louder)\b", lower):
        # Extract optional step, e.g. "volume up by 20"
        step_m = re.search(r"\b(?:by\s+)?([0-9]{1,2})\s*(?:%|percent)?\b", lower)
        step = int(step_m.group(1)) if step_m else 10
        res = adjust_volume(step)
        return {"action": "volume_up", "category": "hardware", "data": res, "reply": res["reply"]}

    # Volume Down
    if re.search(r"\b(?:volume\s+down|decrease\s+(?:the\s+)?volume|lower\s+(?:the\s+)?volume|turn\s+down\s+(?:the\s+)?volume|quieter)\b", lower):
        step_m = re.search(r"\b(?:by\s+)?([0-9]{1,2})\s*(?:%|percent)?\b", lower)
        step = int(step_m.group(1)) if step_m else 10
        res = adjust_volume(-step)
        return {"action": "volume_down", "category": "hardware", "data": res, "reply": res["reply"]}

    # ---------------------------------------------------------
    # 3. HARDWARE: BRIGHTNESS
    # ---------------------------------------------------------
    # Check brightness
    if re.search(r"\b(?:what(?:\'s|\s+is)\s+(?:the\s+)?brightness|check\s+brightness|current\s+brightness)\b", lower):
        status = get_brightness_status()
        reply = f"Current display brightness is {status.get('percent', 100)}%."
        return {"action": "brightness_status", "category": "hardware", "data": status, "reply": reply}

    # Brightness Set (e.g. "set brightness to 80%", "brightness to 50", "brightness 90%")
    bright_set = re.search(r"\b(?:set\s+(?:the\s+)?brightness\s+(?:to\s+)?|change\s+brightness\s+to\s+|brightness\s+(?:to\s+)?)([0-9]{1,3})\s*(?:%|percent)?\b", lower)
    if bright_set:
        pct = int(bright_set.group(1))
        res = set_brightness(pct)
        return {"action": "brightness_set", "category": "hardware", "data": res, "reply": res["reply"]}

    # Brightness Up
    if re.search(r"\b(?:brightness\s+up|increase\s+(?:the\s+)?brightness|raise\s+(?:the\s+)?brightness|turn\s+up\s+(?:the\s+)?brightness|brighter)\b", lower):
        step_m = re.search(r"\b(?:by\s+)?([0-9]{1,2})\s*(?:%|percent)?\b", lower)
        step = int(step_m.group(1)) if step_m else 10
        res = adjust_brightness(step)
        return {"action": "brightness_up", "category": "hardware", "data": res, "reply": res["reply"]}

    # Brightness Down
    if re.search(r"\b(?:brightness\s+down|decrease\s+(?:the\s+)?brightness|lower\s+(?:the\s+)?brightness|turn\s+down\s+(?:the\s+)?brightness|dim\s+(?:the\s+)?(?:screen|display)?)\b", lower):
        step_m = re.search(r"\b(?:by\s+)?([0-9]{1,2})\s*(?:%|percent)?\b", lower)
        step = int(step_m.group(1)) if step_m else 10
        res = adjust_brightness(-step)
        return {"action": "brightness_down", "category": "hardware", "data": res, "reply": res["reply"]}

    # ---------------------------------------------------------
    # 4. WEBSITES & SEARCH
    # ---------------------------------------------------------
    # Explicit web search triggers: "search google for ...", "search youtube for ...", "google ..."
    if re.match(r"^(?:search\s+google|search\s+youtube|google\b)", lower) or re.search(r"\b(?:on\s+google|on\s+youtube|in\s+youtube)\b", lower):
        res = launch_website(clean)
        if res["ok"]:
            target_engine = "youtube" if "youtube" in clean.lower() else "google"
            _safe_save_context(app=target_engine, last_action="search", last_query=clean, last_url=res.get("url", ""))
            return {"action": "launch_website", "category": "web", "data": res, "reply": res["reply"]}

    # ---------------------------------------------------------
    # 5. OPEN APPS OR LAUNCH WEBSITES
    # ---------------------------------------------------------
    # Trigger patterns: "open ...", "launch ...", "start ...", "go to ..."
    open_match = re.match(r"^(?:open\s+up|open|launch|start|go\s+to)\s+(.+)$", clean, re.IGNORECASE)
    if open_match:
        target = open_match.group(1).strip(" \t\r\n.?!,;:\"'`")
        target_lower = target.lower()

        # If user explicitly said "file" or target has a document/file extension, let file manager handle it
        if re.search(r"\b(files?|documents?|docs?|folder|directory)\b", target_lower):
            return None

        for ext in FILE_EXTENSIONS:
            if target_lower.endswith(ext):
                return None

        # Clean words like 'app', 'application', 'the', 'my', 'program'
        app_clean = re.sub(r"^(?:the|my|a|this)\s+", "", target, flags=re.IGNORECASE).strip()
        app_clean = re.sub(r"\s+(?:app|application|program|software)$", "", app_clean, flags=re.IGNORECASE).strip()

        # Check if target is a website
        web_target = resolve_web_target(app_clean)
        if web_target:
            res = launch_website(app_clean)
            if res["ok"]:
                _safe_save_context(app=app_clean, last_action="launch_website", last_url=res.get("url", ""))
                return {"action": "launch_website", "category": "web", "data": res, "reply": res["reply"]}

        # Otherwise, launch application
        res = launch_app(app_clean)
        if res["ok"]:
            _safe_save_context(app=app_clean, last_action="open_app")
            return {"action": "open_app", "category": "app", "data": res, "reply": res["reply"]}

    return None
