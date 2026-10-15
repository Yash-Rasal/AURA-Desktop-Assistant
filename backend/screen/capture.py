from __future__ import annotations

import io
import time
from pathlib import Path

import mss
from PIL import Image

from config import settings


def capture_full_screen() -> tuple[Path, str]:
    """Capture primary monitor; returns (file path, base64 png)."""
    settings.screenshot_path.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    out = settings.screenshot_path / f"screen_{ts}.png"

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)

    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    jpeg_bytes = buf.getvalue()
    
    out_jpg = out.with_suffix(".jpg")
    out_jpg.write_bytes(jpeg_bytes)

    import base64

    return out_jpg, base64.b64encode(jpeg_bytes).decode("ascii")


def capture_active_window() -> tuple[Path, str]:
    """On Windows, full screen is reliable; window-specific capture can be added later."""
    return capture_full_screen()
