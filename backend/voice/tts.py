from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import edge_tts

from config import settings

ROOT = Path(__file__).resolve().parent.parent.parent
TEMP = ROOT / "data" / "temp"
TEMP.mkdir(parents=True, exist_ok=True)


async def synthesize(text: str) -> Path:
    out = TEMP / f"tts_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(text, settings.tts_voice)
    await communicate.save(str(out))
    return out
