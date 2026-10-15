"""Context-aware desktop and browser follow-up action resolution."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional

try:
    from commands.hardware import adjust_volume
    from commands.web import launch_website
    from config import settings
    from flows.state import ContextState
    from memory.session import memory
except ImportError:
    from backend.commands.hardware import adjust_volume
    from backend.commands.web import launch_website
    from backend.config import settings
    from backend.flows.state import ContextState
    from backend.memory.session import memory

logger = logging.getLogger("flows.context_followups")


def save_context(
    app: str = "",
    last_action: str = "",
    last_query: str = "",
    last_url: str = "",
) -> None:
    """Store recent application or web search context into session memory."""
    ctx = ContextState(
        app=app.lower().strip(),
        last_action=last_action.lower().strip(),
        last_query=last_query.strip(),
        last_url=last_url.strip(),
    )
    memory.set_context(ctx)
    logger.debug("Desktop context saved: %s", ctx)


def _ensure_app_foreground(app_hint: str) -> None:
    """Attempt to bring the window matching app_hint to foreground via win32gui."""
    if not app_hint:
        return
    try:
        import win32gui

        matched_hwnd = None
        hint = app_hint.lower()

        def enum_cb(hwnd, _):
            nonlocal matched_hwnd
            if matched_hwnd:
                return
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if hint in title:
                    matched_hwnd = hwnd

        win32gui.EnumWindows(enum_cb, None)
        if matched_hwnd:
            win32gui.SetForegroundWindow(matched_hwnd)
    except Exception as e:
        logger.debug("Could not bring app '%s' to foreground: %s", app_hint, e)


def _send_browser_key(keys: list[str], app_hint: str = "") -> None:
    """Simulate keypress or hotkey in foreground application."""
    import pyautogui
    pyautogui.FAILSAFE = True
    _ensure_app_foreground(app_hint)
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)


async def resolve_followup(text: str, context: Optional[ContextState]) -> Optional[Dict[str, Any]]:
    """
    Resolve context-aware follow-up phrases (e.g. 'now search for jazz', 'scroll down', 'refresh').
    Returns a result dict if handled, or None to pass through to normal pipeline.
    """
    ttl = getattr(settings, "context_ttl_seconds", 120)
    if not context or context.is_expired(ttl):
        return None

    clean = text.strip()
    lower = clean.lower()

    # 1. Search follow-ups: "now search for X", "search for X", "search again"
    search_for_match = re.match(r"^(?:now\s+)?search\s+(?:for\s+)?(.+)$", lower)
    if search_for_match:
        new_query = search_for_match.group(1).strip()
        if new_query in ("again", "it again"):
            new_query = context.last_query

        if new_query:
            # Reuse previous search engine
            if context.app in ("youtube", "yt") or "youtube.com" in context.last_url:
                search_cmd = f"search youtube for {new_query}"
            else:
                search_cmd = f"search google for {new_query}"

            res = launch_website(search_cmd)
            save_context(app=context.app, last_action="search", last_query=new_query, last_url=res.get("url", ""))
            return {
                "action": "search_followup",
                "category": "followup",
                "data": res,
                "reply": f"Searching for '{new_query}'.",
            }

    # 2. Open first result: "open the first one", "open first result", "click the first link"
    if re.search(r"\b(?:open\s+(?:the\s+)?first(?:\s+(?:one|result|link))?|click\s+(?:the\s+)?first)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["tab", "enter"], context.app)
        return {
            "action": "open_first_result",
            "category": "followup",
            "reply": "Opening the first result.",
        }

    # 3. Scrolling: "scroll down", "scroll up", "page down", "page up"
    if re.search(r"\b(?:scroll\s+down|page\s+down)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["pagedown"], context.app)
        return {
            "action": "scroll_down",
            "category": "followup",
            "reply": "Scrolling down.",
        }

    if re.search(r"\b(?:scroll\s+up|page\s+up)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["pageup"], context.app)
        return {
            "action": "scroll_up",
            "category": "followup",
            "reply": "Scrolling up.",
        }

    # 4. Browser Navigation: "go back", "go forward", "refresh", "reload"
    if re.search(r"\b(?:go\s+back|browser\s+back)\b", lower) and not getattr(memory.active_flow, "status", None) == "active":
        await asyncio.to_thread(_send_browser_key, ["alt", "left"], context.app)
        return {
            "action": "browser_back",
            "category": "followup",
            "reply": "Navigating back.",
        }

    if re.search(r"\b(?:go\s+forward|browser\s+forward)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["alt", "right"], context.app)
        return {
            "action": "browser_forward",
            "category": "followup",
            "reply": "Navigating forward.",
        }

    if re.search(r"\b(?:refresh|reload|refresh\s+page)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["f5"], context.app)
        return {
            "action": "browser_refresh",
            "category": "followup",
            "reply": "Refreshing page.",
        }

    # 5. Tab Management: "new tab", "close tab", "next tab", "previous tab"
    if re.search(r"\b(?:new\s+tab|open\s+(?:a\s+)?new\s+tab)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["ctrl", "t"], context.app)
        return {
            "action": "browser_new_tab",
            "category": "followup",
            "reply": "Opened a new tab.",
        }

    if re.search(r"\b(?:close\s+tab|close\s+this\s+tab)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["ctrl", "w"], context.app)
        return {
            "action": "browser_close_tab",
            "category": "followup",
            "reply": "Closed tab.",
        }

    if re.search(r"\b(?:next\s+tab|switch\s+tab)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["ctrl", "tab"], context.app)
        return {
            "action": "browser_next_tab",
            "category": "followup",
            "reply": "Switched to next tab.",
        }

    if re.search(r"\b(?:previous\s+tab|prev\s+tab)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["ctrl", "shift", "tab"], context.app)
        return {
            "action": "browser_prev_tab",
            "category": "followup",
            "reply": "Switched to previous tab.",
        }

    # 6. Fullscreen
    if re.search(r"\b(?:full\s*screen|exit\s+full\s*screen|toggle\s+full\s*screen)\b", lower):
        await asyncio.to_thread(_send_browser_key, ["f11"], context.app)
        return {
            "action": "toggle_fullscreen",
            "category": "followup",
            "reply": "Toggled full screen.",
        }

    # 7. Media Play/Pause
    if re.search(r"\b(?:play\s+pause|play|pause|resume)\b", lower) and context.app in ("youtube", "spotify", "music", "media"):
        await asyncio.to_thread(_send_browser_key, ["playpause"], context.app)
        return {
            "action": "media_play_pause",
            "category": "followup",
            "reply": "Toggled playback.",
        }

    # 8. Volume follow-up: "volume up", "volume down"
    if re.search(r"\b(?:volume\s+up|louder)\b", lower):
        res = adjust_volume(10)
        return {"action": "volume_up", "category": "hardware", "data": res, "reply": res["reply"]}

    if re.search(r"\b(?:volume\s+down|softer|quieter)\b", lower):
        res = adjust_volume(-10)
        return {"action": "volume_down", "category": "hardware", "data": res, "reply": res["reply"]}

    return None
