from __future__ import annotations

import httpx

from config import settings


class OllamaError(Exception):
    pass


async def _post(path: str, payload: dict) -> dict:
    url = f"{settings.ollama_base_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        err_detail = e.response.text
        try:
            err_detail = e.response.json().get("error", e.response.text)
        except Exception:
            pass
        raise OllamaError(f"Ollama error {e.response.status_code}: {err_detail}") from e
    except httpx.RequestError as e:
        raise OllamaError(
            f"Cannot reach Ollama at {settings.ollama_base_url}. "
            "Make sure it is running."
        ) from e


async def chat(messages: list[dict], model: str | None = None) -> str:
    model = model or settings.ollama_chat_model
    data = await _post(
        "/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": 120,
                "temperature": 0.7,
            },
        },
    )
    msg = data.get("message") or {}
    content = msg.get("content", "").strip()
    if not content:
        raise OllamaError("Empty response from Ollama chat model.")
    return content


async def vision(
    prompt: str,
    image_b64: str,
    history: list[dict] | None = None,
    model: str | None = None,
) -> str:
    model = model or settings.ollama_vision_model
    messages: list[dict] = []

    if history:
        for h in history[-6:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append(
        {
            "role": "user",
            "content": prompt,
            "images": [image_b64],
        }
    )

    data = await _post(
        "/api/chat",
        {"model": model, "messages": messages, "stream": False},
    )
    msg = data.get("message") or {}
    content = msg.get("content", "").strip()
    if not content:
        raise OllamaError("Empty response from Ollama vision model.")
    return content


async def health_check() -> dict:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return {"ok": True, "models": models}
    except httpx.HTTPError:
        return {"ok": False, "models": []}
