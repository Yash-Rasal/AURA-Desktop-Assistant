from __future__ import annotations

import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from config import settings

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8" if settings.whisper_device == "cpu" else "float16",
        )
    return _model


def transcribe_audio_file(path: Path) -> str:
    model = _get_model()
    lang = getattr(settings, "whisper_language", "en")
    segments, _info = model.transcribe(
        str(path),
        language=lang,
        beam_size=5,
        vad_filter=True,
        initial_prompt="Open Chrome, open Gmail, open email, volume up, brightness down, write an email, search YouTube.",
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text or "(no speech detected)"
