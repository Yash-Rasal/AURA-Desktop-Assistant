# Desktop AI Companion

Personal floating desktop assistant: screen-aware chat, global hotkeys, local voice (Whisper + edge-tts), and **Ollama** for AI (no OpenAI required).

## Prerequisites

1. **Node.js** 18+ and **Python** 3.10+
2. **Ollama** — [https://ollama.com](https://ollama.com)

```powershell
ollama serve
ollama pull llama3.2
ollama pull llava
```

Adjust model names in `.env` if you use different tags.

## Quick start (Windows)

```powershell
cd C:\Users\yashr\Projects\desktop-ai-assistant
.\scripts\setup.ps1
.\scripts\start.ps1
```

Or manually:

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example ..\.env
python run.py

# Frontend (new terminal)
cd frontend\electron-app
npm install
npm start
```

## Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+A` | Toggle companion window |
| `Ctrl+Shift+S` | Screenshot + vision analysis |
| `Ctrl+Shift+V` | Push-to-talk voice |

## Quick Commands

Speak naturally or type directly to execute instant desktop controls:

| Category | Example Phrases |
|----------|-----------------|
| **Open Apps** | `open chrome`, `launch notepad`, `open calculator`, `open spotify`, `start vs code` |
| **Websites & Search** | `open youtube`, `launch github`, `open reddit`, `search google for python`, `google latest news` |
| **Volume Control** | `volume up`, `volume down`, `set volume to 60%`, `mute`, `unmute`, `current volume` |
| **Brightness Control** | `increase brightness`, `decrease brightness`, `set brightness to 80%`, `dim screen` |
| **Power Management** | `lock pc`, `lock screen`, `put computer to sleep`, `shut down pc`, `restart computer`, `cancel shutdown` |

## Configuration

Copy `.env.example` to `.env` at the project root:

- `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_VISION_MODEL`
- `WHISPER_MODEL` (e.g. `base`, `small`)
- `TTS_VOICE` (edge-tts voice name)

## Architecture

- **Electron** — overlay UI, tray, global shortcuts
- **Python FastAPI** — screenshots, Ollama, Whisper, TTS, session memory
- **Ollama** — local chat + vision

## Privacy

Screenshots are stored under `data/screenshots/` during the session. Clear via Settings → Clear session memory, or delete that folder.
