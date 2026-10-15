from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Static dictionary of well-known applications, system tools, and protocol schemes
KNOWN_APPS: Dict[str, Dict[str, Any]] = {
    "chrome": {"title": "Google Chrome", "exe": "chrome.exe", "launch": "chrome"},
    "google chrome": {"title": "Google Chrome", "exe": "chrome.exe", "launch": "chrome"},
    "edge": {"title": "Microsoft Edge", "exe": "msedge.exe", "launch": "msedge"},
    "microsoft edge": {"title": "Microsoft Edge", "exe": "msedge.exe", "launch": "msedge"},
    "firefox": {"title": "Mozilla Firefox", "exe": "firefox.exe", "launch": "firefox"},
    "brave": {"title": "Brave Browser", "exe": "brave.exe", "launch": "brave"},
    "spotify": {"title": "Spotify", "uri": "spotify:", "exe": "spotify.exe", "launch": "spotify:"},
    "discord": {"title": "Discord", "uri": "discord:", "exe": "discord.exe", "launch": "discord:"},
    "notepad": {"title": "Notepad", "exe": "notepad.exe", "launch": "notepad.exe"},
    "calculator": {"title": "Calculator", "exe": "calc.exe", "launch": "calc.exe"},
    "calc": {"title": "Calculator", "exe": "calc.exe", "launch": "calc.exe"},
    "paint": {"title": "Paint", "exe": "mspaint.exe", "launch": "mspaint.exe"},
    "mspaint": {"title": "Paint", "exe": "mspaint.exe", "launch": "mspaint.exe"},
    "task manager": {"title": "Task Manager", "exe": "taskmgr.exe", "launch": "taskmgr.exe"},
    "taskmgr": {"title": "Task Manager", "exe": "taskmgr.exe", "launch": "taskmgr.exe"},
    "settings": {"title": "Windows Settings", "uri": "ms-settings:", "launch": "ms-settings:"},
    "windows settings": {"title": "Windows Settings", "uri": "ms-settings:", "launch": "ms-settings:"},
    "explorer": {"title": "File Explorer", "exe": "explorer.exe", "launch": "explorer.exe"},
    "file explorer": {"title": "File Explorer", "exe": "explorer.exe", "launch": "explorer.exe"},
    "my computer": {"title": "File Explorer", "exe": "explorer.exe", "launch": "explorer.exe"},
    "terminal": {"title": "Windows Terminal", "exe": "wt.exe", "launch": "wt.exe"},
    "windows terminal": {"title": "Windows Terminal", "exe": "wt.exe", "launch": "wt.exe"},
    "cmd": {"title": "Command Prompt", "exe": "cmd.exe", "launch": "cmd.exe"},
    "command prompt": {"title": "Command Prompt", "exe": "cmd.exe", "launch": "cmd.exe"},
    "powershell": {"title": "PowerShell", "exe": "powershell.exe", "launch": "powershell.exe"},
    "vs code": {"title": "Visual Studio Code", "exe": "code.cmd", "launch": "code"},
    "vscode": {"title": "Visual Studio Code", "exe": "code.cmd", "launch": "code"},
    "code": {"title": "Visual Studio Code", "exe": "code.cmd", "launch": "code"},
    "visual studio code": {"title": "Visual Studio Code", "exe": "code.cmd", "launch": "code"},
    "steam": {"title": "Steam", "uri": "steam:", "exe": "steam.exe", "launch": "steam:"},
    "word": {"title": "Microsoft Word", "exe": "winword.exe", "launch": "winword.exe"},
    "excel": {"title": "Microsoft Excel", "exe": "excel.exe", "launch": "excel.exe"},
    "powerpoint": {"title": "Microsoft PowerPoint", "exe": "powerpnt.exe", "launch": "powerpnt.exe"},
    "obs": {"title": "OBS Studio", "exe": "obs64.exe", "launch": "obs64.exe"},
    "vlc": {"title": "VLC Media Player", "exe": "vlc.exe", "launch": "vlc"},
    "snipping tool": {"title": "Snipping Tool", "exe": "snippingtool.exe", "launch": "snippingtool.exe"},
    "camera": {"title": "Camera", "uri": "microsoft.windows.camera:", "launch": "microsoft.windows.camera:"},
}

_start_menu_cache: Dict[str, str] = {}
_cache_populated = False


def _populate_start_menu_cache() -> None:
    """Scan Windows Start Menu and user programs for .lnk shortcuts."""
    global _cache_populated, _start_menu_cache
    if _cache_populated:
        return

    scopes = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
    ]

    for scope in scopes:
        if not scope.exists():
            continue
        try:
            for p in scope.rglob("*.lnk"):
                name = p.stem.lower().strip()
                if name and name not in _start_menu_cache:
                    _start_menu_cache[name] = str(p)
        except Exception:
            continue

    _cache_populated = True


def find_app_target(app_query: str) -> Optional[Dict[str, Any]]:
    """
    Find launch target for an application query.
    Checks:
    1. Known apps dictionary
    2. Start menu shortcuts
    3. System PATH via shutil.which
    """
    clean = app_query.strip().lower()
    if not clean:
        return None

    # 1. Exact match in known apps
    if clean in KNOWN_APPS:
        return {
            "name": KNOWN_APPS[clean]["title"],
            "target": KNOWN_APPS[clean]["launch"],
            "is_uri": "uri" in KNOWN_APPS[clean],
        }

    # 2. Check Start Menu cache
    _populate_start_menu_cache()

    # Exact match in start menu
    if clean in _start_menu_cache:
        return {
            "name": Path(_start_menu_cache[clean]).stem,
            "target": _start_menu_cache[clean],
            "is_uri": False,
        }

    # Partial / substring match in start menu (e.g. "chrome" matches "Google Chrome")
    for name, path in _start_menu_cache.items():
        if clean == name or clean in name or name in clean:
            return {
                "name": Path(path).stem,
                "target": path,
                "is_uri": False,
            }

    # 3. Check system PATH
    which_target = shutil.which(clean) or shutil.which(f"{clean}.exe")
    if which_target:
        return {
            "name": clean.capitalize(),
            "target": which_target,
            "is_uri": False,
        }

    # Fallback to direct Windows launch
    return {
        "name": clean.capitalize(),
        "target": clean,
        "is_uri": False,
    }


def launch_app(app_query: str) -> Dict[str, Any]:
    """
    Launch an application on Windows.
    Returns result dict with status and conversational reply.
    """
    target_info = find_app_target(app_query)
    if not target_info:
        return {
            "ok": False,
            "name": app_query,
            "error": f"Could not locate application '{app_query}'.",
            "reply": f"I couldn't find an application named '{app_query}'.",
        }

    target = target_info["target"]
    display_name = target_info["name"]

    try:
        # Check if target is a file or URI scheme
        if target.endswith(".lnk") or target_info.get("is_uri") or (":/" in target or target.endswith(":")):
            os.startfile(target)
        else:
            # Launch detached process without blocking
            if shutil.which(target):
                subprocess.Popen(
                    [target],
                    shell=True,
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
            else:
                # Use Windows 'start' via cmd
                subprocess.Popen(
                    f'start "" "{target}"',
                    shell=True,
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )

        return {
            "ok": True,
            "name": display_name,
            "target": target,
            "reply": f"Opening {display_name}.",
        }
    except Exception as e:
        return {
            "ok": False,
            "name": display_name,
            "error": str(e),
            "reply": f"Failed to open {display_name}: {str(e)}",
        }
