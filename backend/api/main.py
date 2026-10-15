from __future__ import annotations

import asyncio
import logging
import queue
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("api.main")

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import settings
from memory.session import memory
from screen.capture import capture_full_screen
from vision import ollama_client
from system import get_system_stats, get_system_summary
from notifications import send_notification
from files import (
    handle_file_intent,
    find_files,
    open_in_explorer,
    open_file,
    rename_file,
    organize_directory,
    summarize_document,
)
from commands import (
    handle_quick_command,
    launch_app,
    launch_website,
    get_volume_status,
    set_volume,
    adjust_volume,
    set_mute,
    get_brightness_status,
    set_brightness,
    adjust_brightness,
    lock_workstation,
    sleep_computer,
    shutdown_computer,
    restart_computer,
    cancel_shutdown,
)

# Start background voice loop
from voice import loop
loop.start_loop()

app = FastAPI(title="Desktop AI Companion API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = (
    "You are a helpful desktop AI companion. The user speaks to you via voice. "
    "Always communicate and respond in English. "
    "Keep answers natural, direct, and concise (1 to 3 short sentences maximum), suitable for spoken text-to-speech. "
    "Do not use markdown tables, bullet points, or lengthy intros unless explicitly asked."
)


class ChatRequest(BaseModel):
    message: str
    use_screen: bool = False


class VisionRequest(BaseModel):
    message: str
    capture: bool = True


class SpeakRequest(BaseModel):
    text: str


class NotifyRequest(BaseModel):
    title: str = "Desktop AI Companion"
    message: str


_active_voice_ws: set[WebSocket] = set()

async def _voice_events_broadcaster():
    while True:
        try:
            event = await asyncio.to_thread(loop.events.get, True, 1.0)
        except queue.Empty:
            continue
        except Exception:
            await asyncio.sleep(0.5)
            continue

        if _active_voice_ws:
            dead = []
            for ws in list(_active_voice_ws):
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _active_voice_ws.discard(ws)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_voice_events_broadcaster())

@app.post("/voice/trigger")
async def manual_trigger():
    loop.force_trigger()
    return {"ok": True}

@app.websocket("/voice/events")
async def voice_events(websocket: WebSocket):
    await websocket.accept()
    _active_voice_ws.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _active_voice_ws.discard(websocket)

@app.get("/health")
async def health():
    ollama = await ollama_client.health_check()
    return {
        "status": "ok",
        "ollama": ollama,
        "chat_model": settings.ollama_chat_model,
        "vision_model": settings.ollama_vision_model,
    }


class FileOpenRequest(BaseModel):
    path: str

class FileRenameRequest(BaseModel):
    target: str
    new_name: str

class FileOrganizeRequest(BaseModel):
    target: str = "downloads"

class FileSummarizeRequest(BaseModel):
    target: str

class QuickCommandRequest(BaseModel):
    command: str

class AppOpenRequest(BaseModel):
    app: str

class WebLaunchRequest(BaseModel):
    query: str

class VolumeControlRequest(BaseModel):
    percent: int | None = None
    delta: int | None = None
    mute: bool | None = None

class BrightnessControlRequest(BaseModel):
    percent: int | None = None
    delta: int | None = None

class PowerControlRequest(BaseModel):
    action: str  # "lock", "sleep", "shutdown", "restart", "cancel"
    delay: int = 20

@app.post("/chat")
async def chat(req: ChatRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Message is required.")

    # 0. Guided Multi-Turn Flows & Context Follow-ups (if enabled)
    if getattr(settings, "flows_enabled", True):
        try:
            try:
                from flows import handle_flow_or_followup, FlowResponse
            except ImportError:
                from backend.flows import handle_flow_or_followup, FlowResponse

            flow_res = await handle_flow_or_followup(text, memory)
            if flow_res:
                if isinstance(flow_res, FlowResponse):
                    reply = flow_res.reply_text
                    memory.add_message("user", text)
                    memory.add_message("assistant", reply)
                    return flow_res.to_dict()
                elif isinstance(flow_res, dict):
                    reply = flow_res.get("reply", "")
                    memory.add_message("user", text)
                    memory.add_message("assistant", reply)
                    return flow_res
        except Exception as e:
            logger.exception("Flow handling exception: %s", e)

    # 1. Fast dispatch for Quick Commands (apps, websites, volume, brightness, power)
    quick_cmd = await handle_quick_command(text)
    if quick_cmd:
        reply = quick_cmd["reply"]
        memory.add_message("user", text)
        memory.add_message("assistant", reply)
        return {
            "reply": reply,
            "quick_command": quick_cmd,
        }

    # 2. Fast dispatch for File Management actions (find, rename, organize, summarize)
    file_action = await handle_file_intent(text)
    if file_action:
        reply = file_action["reply"]
        memory.add_message("user", text)
        memory.add_message("assistant", reply)
        return {
            "reply": reply,
            "file_action": file_action,
        }

    temp_context = memory.chat_context()
    temp_context.append({"role": "user", "content": text})

    lower_text = text.lower()
    system_ctx = ""
    if any(k in lower_text for k in ["cpu", "ram", "memory", "battery", "disk", "hardware", "system specs", "specs", "performance", "task manager", "processes", "system stats"]):
        system_ctx = f"\n\n[Live System Telemetry: {get_system_summary()}]"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + system_ctx}, *temp_context]

    if req.use_screen:
        b64 = memory.last_screenshot_b64()
        if not b64:
            _, b64 = await asyncio.to_thread(capture_full_screen)
        try:
            reply = await ollama_client.vision(
                text,
                b64,
                history=temp_context[:-1],
            )
        except ollama_client.OllamaError as e:
            raise HTTPException(503, str(e)) from e
    else:
        try:
            reply = await ollama_client.chat(messages)
        except ollama_client.OllamaError as e:
            raise HTTPException(503, str(e)) from e

    memory.add_message("user", text)
    memory.add_message("assistant", reply)
    return {"reply": reply}


@app.get("/files/search")
async def file_search(q: str):
    return find_files(q)


@app.post("/files/open")
async def file_open(req: FileOpenRequest):
    ok = open_in_explorer(req.path)
    return {"ok": ok}


@app.post("/files/launch")
async def file_launch(req: FileOpenRequest):
    ok = open_file(req.path)
    return {"ok": ok}


@app.post("/files/rename")
async def file_rename_endpoint(req: FileRenameRequest):
    return rename_file(req.target, req.new_name)


@app.post("/files/organize")
async def file_organize_endpoint(req: FileOrganizeRequest):
    return organize_directory(req.target)


@app.post("/files/summarize")
async def file_summarize_endpoint(req: FileSummarizeRequest):
    return await summarize_document(req.target)


# ---------------------------------------------------------
# Quick Command Endpoints
# ---------------------------------------------------------

@app.post("/commands/execute")
async def command_execute_endpoint(req: QuickCommandRequest):
    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "Command text is required.")
    res = await handle_quick_command(cmd)
    if not res:
        return {"ok": False, "reply": f"Could not match a quick command for '{cmd}'."}
    return res


@app.post("/commands/apps/open")
async def app_open_endpoint(req: AppOpenRequest):
    app_name = req.app.strip()
    if not app_name:
        raise HTTPException(400, "App name is required.")
    return launch_app(app_name)


@app.post("/commands/web/launch")
async def web_launch_endpoint(req: WebLaunchRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(400, "Query is required.")
    return launch_website(query)


@app.get("/commands/hardware/status")
async def hardware_status_endpoint():
    return {
        "volume": get_volume_status(),
        "brightness": get_brightness_status(),
    }


@app.post("/commands/hardware/volume")
async def hardware_volume_endpoint(req: VolumeControlRequest):
    if req.mute is not None:
        return set_mute(req.mute)
    if req.percent is not None:
        return set_volume(req.percent)
    if req.delta is not None:
        return adjust_volume(req.delta)
    return get_volume_status()


@app.post("/commands/hardware/brightness")
async def hardware_brightness_endpoint(req: BrightnessControlRequest):
    if req.percent is not None:
        return set_brightness(req.percent)
    if req.delta is not None:
        return adjust_brightness(req.delta)
    return get_brightness_status()


@app.post("/commands/power")
async def power_endpoint(req: PowerControlRequest):
    action = req.action.lower().strip()
    if action == "lock":
        return lock_workstation()
    elif action == "sleep":
        return sleep_computer()
    elif action == "shutdown":
        return shutdown_computer(delay_seconds=req.delay)
    elif action == "restart":
        return restart_computer(delay_seconds=req.delay)
    elif action == "cancel":
        return cancel_shutdown()
    else:
        raise HTTPException(400, f"Unsupported power action: '{action}'. Must be lock, sleep, shutdown, restart, or cancel.")


@app.post("/vision")
async def vision_analyze(req: VisionRequest):
    text = req.message.strip() or "Describe what you see on this screen and how you can help."
    if req.capture:
        path, b64 = await asyncio.to_thread(capture_full_screen)
        memory.add_screenshot(str(path), b64)
    else:
        b64 = memory.last_screenshot_b64()
        if not b64:
            raise HTTPException(400, "No screenshot available. Capture one first.")

    try:
        reply = await ollama_client.vision(text, b64, history=memory.chat_context())
    except ollama_client.OllamaError as e:
        raise HTTPException(503, str(e)) from e

    memory.add_message("user", text)
    memory.add_message("assistant", reply)
    return {"reply": reply, "screenshot": memory.recent_screenshots[-1]["path"] if memory.recent_screenshots else None}


@app.post("/screenshot")
async def screenshot():
    path, b64 = await asyncio.to_thread(capture_full_screen)
    memory.add_screenshot(str(path), b64)
    return {"path": str(path), "preview": f"data:image/jpeg;base64,{b64}"}


@app.post("/voice/transcribe")
async def transcribe(file: UploadFile = File(...)):
    temp_dir = Path(settings.screenshot_path).parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    dest = temp_dir / f"rec_{id(file)}{suffix}"
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        from voice import stt

        text = await asyncio.to_thread(stt.transcribe_audio_file, dest)
        return {"text": text}
    finally:
        if dest.exists():
            dest.unlink(missing_ok=True)


@app.post("/voice/speak")
async def speak(req: SpeakRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Text is required.")
    from voice import tts
    from starlette.background import BackgroundTask
    import os

    loop.set_muted(True) # Mute loop while generating/playing TTS
    try:
        path = await tts.synthesize(text)
        
        def cleanup():
            os.remove(path)
            # We must unmute AFTER it plays on the client side, so the client calls /voice/unmute
            # Or we can just sleep a bit, but better to add a new endpoint
        
        return FileResponse(
            path,
            media_type="audio/mpeg",
            filename=path.name,
            background=BackgroundTask(cleanup)
        )
    except Exception:
        loop.set_muted(False)
        raise

@app.post("/voice/unmute")
async def unmute():
    loop.set_muted(False)
    return {"ok": True}


@app.get("/system/stats")
async def system_stats():
    return get_system_stats()


@app.get("/system/summary")
async def system_summary_endpoint():
    return {"summary": get_system_summary()}


@app.post("/system/notify")
async def desktop_notify(req: NotifyRequest):
    msg = req.message.strip()
    if not msg:
        raise HTTPException(400, "Message cannot be empty.")
    success = await send_notification(req.title, msg)
    return {"ok": success}


@app.post("/memory/clear")
async def clear_memory():
    memory.clear()
    return {"ok": True}


@app.get("/memory/status")
async def memory_status():
    return {
        "messages": len(memory.messages),
        "screenshots": len(memory.recent_screenshots),
    }


class FlowStartRequest(BaseModel):
    flow_name: str = "email"
    slots: Optional[dict[str, Any]] = None

FlowStartRequest.model_rebuild()


@app.post("/flow/start")
async def flow_start(req: FlowStartRequest):
    if not getattr(settings, "flows_enabled", True):
        raise HTTPException(400, "Flows are disabled.")
    try:
        try:
            from flows import FlowEngine
        except ImportError:
            from backend.flows import FlowEngine

        res = FlowEngine.start(req.flow_name, memory, req.slots)
        memory.add_message("assistant", res.reply_text)
        return res.to_dict()
    except Exception as e:
        logger.exception("Error starting flow: %s", e)
        raise HTTPException(500, str(e)) from e


@app.post("/flow/cancel")
async def flow_cancel():
    if not getattr(settings, "flows_enabled", True):
        raise HTTPException(400, "Flows are disabled.")
    try:
        memory.clear_active_flow()
        return {"ok": True, "reply": "Flow cancelled."}
    except Exception as e:
        logger.exception("Error cancelling flow: %s", e)
        raise HTTPException(500, str(e)) from e


@app.get("/flow/state")
async def flow_state():
    if not getattr(settings, "flows_enabled", True):
        return {"active": False, "flows_enabled": False}
    active_flow = getattr(memory, "active_flow", None)
    if active_flow:
        return {
            "active": getattr(active_flow, "status", "") == "active",
            "flow_name": getattr(active_flow, "flow_name", ""),
            "step_index": getattr(active_flow, "step_index", 0),
            "slots": getattr(active_flow, "slots", {}),
            "status": getattr(active_flow, "status", ""),
        }
    return {"active": False, "flow": None}

