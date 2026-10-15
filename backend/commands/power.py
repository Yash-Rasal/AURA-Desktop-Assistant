from __future__ import annotations

import ctypes
import os
import subprocess
from typing import Any, Dict


def lock_workstation() -> Dict[str, Any]:
    """Instantly lock the Windows workstation."""
    try:
        # Use native user32 LockWorkStation
        success = bool(ctypes.windll.user32.LockWorkStation())
        if success:
            return {
                "ok": True,
                "action": "lock",
                "reply": "Locking your computer.",
            }
        else:
            # Fallback rundll32
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return {
                "ok": True,
                "action": "lock",
                "reply": "Locking your computer.",
            }
    except Exception as e:
        return {
            "ok": False,
            "action": "lock",
            "error": str(e),
            "reply": f"Failed to lock workstation: {str(e)}",
        }


def sleep_computer() -> Dict[str, Any]:
    """Put computer into sleep/suspend state."""
    try:
        # rundll32.exe powrprof.dll,SetSuspendState 0,1,0
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return {
            "ok": True,
            "action": "sleep",
            "reply": "Putting your computer to sleep.",
        }
    except Exception as e:
        return {
            "ok": False,
            "action": "sleep",
            "error": str(e),
            "reply": f"Failed to put computer to sleep: {str(e)}",
        }


def shutdown_computer(delay_seconds: int = 20) -> Dict[str, Any]:
    """
    Schedule system shutdown with a safety delay window so it can be aborted if accidental.
    """
    try:
        subprocess.run(
            ["shutdown.exe", "/s", "/t", str(delay_seconds), "/c", "Shutting down by Desktop AI Companion"],
            check=True,
        )
        return {
            "ok": True,
            "action": "shutdown",
            "delay": delay_seconds,
            "reply": f"Shutting down your computer in {delay_seconds} seconds. Say 'cancel shutdown' to abort.",
        }
    except Exception as e:
        return {
            "ok": False,
            "action": "shutdown",
            "error": str(e),
            "reply": f"Failed to initiate shutdown: {str(e)}",
        }


def restart_computer(delay_seconds: int = 15) -> Dict[str, Any]:
    """
    Schedule system restart with a safety delay window so it can be aborted if accidental.
    """
    try:
        subprocess.run(
            ["shutdown.exe", "/r", "/t", str(delay_seconds), "/c", "Restarting by Desktop AI Companion"],
            check=True,
        )
        return {
            "ok": True,
            "action": "restart",
            "delay": delay_seconds,
            "reply": f"Restarting your computer in {delay_seconds} seconds. Say 'cancel shutdown' to abort.",
        }
    except Exception as e:
        return {
            "ok": False,
            "action": "restart",
            "error": str(e),
            "reply": f"Failed to initiate restart: {str(e)}",
        }


def cancel_shutdown() -> Dict[str, Any]:
    """Abort an in-progress scheduled shutdown or restart."""
    try:
        res = subprocess.run(["shutdown.exe", "/a"], capture_output=True, text=True)
        if res.returncode == 0:
            return {
                "ok": True,
                "action": "cancel_shutdown",
                "reply": "Scheduled shutdown or restart has been cancelled.",
            }
        else:
            return {
                "ok": True,
                "action": "cancel_shutdown",
                "reply": "No scheduled shutdown or restart is currently active.",
            }
    except Exception as e:
        return {
            "ok": False,
            "action": "cancel_shutdown",
            "error": str(e),
            "reply": f"Failed to cancel shutdown: {str(e)}",
        }
