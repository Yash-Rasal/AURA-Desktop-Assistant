from __future__ import annotations

from .apps import launch_app, find_app_target
from .web import launch_website, resolve_web_target
from .hardware import (
    get_volume_status,
    set_volume,
    adjust_volume,
    set_mute,
    get_brightness_status,
    set_brightness,
    adjust_brightness,
)
from .power import (
    lock_workstation,
    sleep_computer,
    shutdown_computer,
    restart_computer,
    cancel_shutdown,
)
from .dispatcher import handle_quick_command

__all__ = [
    "launch_app",
    "find_app_target",
    "launch_website",
    "resolve_web_target",
    "get_volume_status",
    "set_volume",
    "adjust_volume",
    "set_mute",
    "get_brightness_status",
    "set_brightness",
    "adjust_brightness",
    "lock_workstation",
    "sleep_computer",
    "shutdown_computer",
    "restart_computer",
    "cancel_shutdown",
    "handle_quick_command",
]
