"""Unit tests for context follow-ups with simulated browser and app actions."""
import time
from unittest.mock import patch, MagicMock
import pytest

from backend.flows.context_followups import resolve_followup, save_context
from backend.flows.state import ContextState
from backend.memory.session import memory


@pytest.mark.asyncio
async def test_search_followup_youtube():
    ctx = ContextState(
        app="youtube",
        last_action="search",
        last_query="lofi hip hop",
        last_url="https://youtube.com/results?search_query=lofi+hip+hop",
    )

    with patch("backend.commands.web.webbrowser.open", return_value=True) as mock_open:
        res = await resolve_followup("now search for jazz", ctx)
        assert res is not None
        assert res["action"] == "search_followup"
        assert "jazz" in res["reply"]
        assert mock_open.called
        # Verify URL opened contains youtube and jazz
        called_url = mock_open.call_args[0][0]
        assert "youtube.com" in called_url
        assert "jazz" in called_url


@pytest.mark.asyncio
async def test_search_again():
    ctx = ContextState(
        app="google",
        last_action="search",
        last_query="weather tomorrow",
        last_url="https://www.google.com/search?q=weather+tomorrow",
    )

    with patch("backend.commands.web.webbrowser.open", return_value=True) as mock_open:
        res = await resolve_followup("search again", ctx)
        assert res is not None
        assert res["action"] == "search_followup"
        assert mock_open.called


@pytest.mark.asyncio
async def test_browser_hotkeys_mocked():
    ctx = ContextState(
        app="chrome",
        last_action="open_app",
        timestamp=time.time(),
    )

    with patch("pyautogui.press") as mock_press, patch("pyautogui.hotkey") as mock_hotkey, patch("backend.flows.context_followups._ensure_app_foreground"):
        # Scroll down
        res_scroll = await resolve_followup("scroll down", ctx)
        assert res_scroll is not None
        assert res_scroll["action"] == "scroll_down"
        mock_press.assert_called_with("pagedown")

        # New tab
        res_tab = await resolve_followup("new tab", ctx)
        assert res_tab is not None
        assert res_tab["action"] == "browser_new_tab"
        mock_hotkey.assert_called_with("ctrl", "t")

        # Close tab
        res_close = await resolve_followup("close tab", ctx)
        assert res_close is not None
        assert res_close["action"] == "browser_close_tab"
        mock_hotkey.assert_called_with("ctrl", "w")

        # Refresh
        res_refresh = await resolve_followup("refresh", ctx)
        assert res_refresh is not None
        assert res_refresh["action"] == "browser_refresh"
        mock_press.assert_called_with("f5")


@pytest.mark.asyncio
async def test_context_expiration():
    old_ctx = ContextState(
        app="chrome",
        last_action="open_app",
        timestamp=time.time() - 150,  # Expired (> 120s)
    )

    res = await resolve_followup("scroll down", old_ctx)
    assert res is None  # Should fall through to normal pipeline
