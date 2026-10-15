from __future__ import annotations

import subprocess
from typing import Any, Dict

# -------------------------------------------------------------
# Master Volume Control (via pycaw)
# -------------------------------------------------------------

def _get_audio_endpoint():
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass
    from pycaw.pycaw import AudioUtilities
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


def get_volume_status() -> Dict[str, Any]:
    """Retrieve current master volume percent and mute state."""
    try:
        endpoint = _get_audio_endpoint()
        scalar = endpoint.GetMasterVolumeLevelScalar()
        percent = int(round(scalar * 100))
        muted = bool(endpoint.GetMute())
        return {"ok": True, "percent": percent, "muted": muted}
    except Exception as e:
        return {"ok": False, "percent": 50, "muted": False, "error": str(e)}


def set_volume(percent: int) -> Dict[str, Any]:
    """Set master volume to an exact percentage (0-100)."""
    percent = max(0, min(100, int(percent)))
    try:
        endpoint = _get_audio_endpoint()
        endpoint.SetMasterVolumeLevelScalar(percent / 100.0, None)
        if endpoint.GetMute():
            endpoint.SetMute(0, None)
        return {
            "ok": True,
            "percent": percent,
            "muted": False,
            "reply": f"Volume set to {percent}%.",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "reply": f"Failed to set volume: {str(e)}",
        }


def adjust_volume(delta: int) -> Dict[str, Any]:
    """Increase or decrease master volume by delta percent."""
    status = get_volume_status()
    current = status.get("percent", 50)
    new_pct = max(0, min(100, current + delta))
    res = set_volume(new_pct)
    if res["ok"]:
        direction = "increased" if delta > 0 else "decreased"
        res["reply"] = f"Volume {direction} to {new_pct}%."
    return res


def set_mute(mute: bool) -> Dict[str, Any]:
    """Mute or unmute master volume."""
    try:
        endpoint = _get_audio_endpoint()
        endpoint.SetMute(1 if mute else 0, None)
        action_word = "muted" if mute else "unmuted"
        return {
            "ok": True,
            "muted": mute,
            "reply": f"Audio {action_word}.",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "reply": f"Failed to {'mute' if mute else 'unmute'} audio: {str(e)}",
        }


# -------------------------------------------------------------
# Display Brightness Control (via screen-brightness-control + WMI)
# -------------------------------------------------------------

def get_brightness_status() -> Dict[str, Any]:
    """Retrieve current display brightness percent."""
    # 1. Try screen-brightness-control library
    try:
        import screen_brightness_control as sbc
        val = sbc.get_brightness()
        if isinstance(val, list) and len(val) > 0:
            return {"ok": True, "percent": int(val[0])}
        elif isinstance(val, (int, float)):
            return {"ok": True, "percent": int(val)}
    except Exception:
        pass

    # 2. Fallback to PowerShell WMI
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"'
        res = subprocess.check_output(cmd, shell=True, text=True, timeout=3).strip()
        if res.isdigit():
            return {"ok": True, "percent": int(res)}
    except Exception:
        pass

    return {"ok": False, "percent": 100, "error": "Could not query brightness"}


def set_brightness(percent: int) -> Dict[str, Any]:
    """Set display brightness to an exact percentage (0-100)."""
    percent = max(0, min(100, int(percent)))

    # 1. Try screen-brightness-control
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(percent)
        return {
            "ok": True,
            "percent": percent,
            "reply": f"Brightness set to {percent}%.",
        }
    except Exception:
        pass

    # 2. Fallback to PowerShell WMI
    try:
        cmd = f'powershell -NoProfile -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {percent})"'
        subprocess.run(cmd, shell=True, check=True, timeout=4)
        return {
            "ok": True,
            "percent": percent,
            "reply": f"Brightness set to {percent}%.",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "reply": f"Failed to set brightness: {str(e)}",
        }


def adjust_brightness(delta: int) -> Dict[str, Any]:
    """Increase or decrease brightness by delta percent."""
    curr = get_brightness_status().get("percent", 100)
    new_pct = max(0, min(100, curr + delta))
    res = set_brightness(new_pct)
    if res["ok"]:
        direction = "increased" if delta > 0 else "decreased"
        res["reply"] = f"Brightness {direction} to {new_pct}%."
    return res
