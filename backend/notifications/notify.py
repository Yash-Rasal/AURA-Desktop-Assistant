from __future__ import annotations

import asyncio
from typing import Optional
from desktop_notifier import DesktopNotifier

_notifier: Optional[DesktopNotifier] = None


def get_notifier() -> DesktopNotifier:
    global _notifier
    if _notifier is None:
        _notifier = DesktopNotifier(app_name="Desktop AI Companion")
    return _notifier


async def send_notification(title: str, message: str) -> bool:
    """Send a native local desktop notification without external services."""
    try:
        notifier = get_notifier()
        await notifier.send(
            title=title or "Desktop AI Companion",
            message=message or "",
        )
        return True
    except Exception as e:
        print(f"[Notifier] Failed to send desktop notification: {e}")
        return False


def send_notification_sync(title: str, message: str) -> bool:
    """Synchronous helper to send notification from non-async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(send_notification(title, message))
            return True
        else:
            return loop.run_until_complete(send_notification(title, message))
    except Exception as e:
        print(f"[Notifier] Sync notification error: {e}")
        return False
