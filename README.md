# AURA - AI Desktop Assistant (v2.0)

AURA (AI Universal Response Assistant) is an autonomous, floating desktop AI companion for Windows featuring **screen-aware vision**, **hands-free voice interaction**, **one-shot quick commands**, and **guided multi-turn conversational flows** (such as drafting emails step-by-step with fuzzy control words).

Built entirely on local privacy-first inference with **Ollama** (Llama 3.2 & LLaVA), **openWakeWord**, **Faster-Whisper (base.en)**, and **Edge-TTS**.

---

## 🌟 Key Features

- 🤖 **Floating Mechanical Companion Overlay**: Draggable, animated always-on-top desktop overlay with speech bubbles, robot eye states, and collapsible chat drawer.
- 🗣️ **Local Hands-Free Voice Control**:
  - Continuous wake-word detection (`"Hey Jarvis"` / `"Alexa"`) via `openWakeWord`.
  - Fast, dedicated English speech-to-text with `faster-whisper` (`base.en`).
  - Natural neural voice responses powered by Microsoft `edge-tts`.
- 🔄 **Guided Multi-Turn Flows**:
  - Conversational step-by-step task completion (e.g. *"write an email to alex@example.com"*).
  - Collects recipient, subject, and multiline body with speech normalizers.
  - Understands fuzzy control words at any turn: *"done"*, *"back"*, *"skip"*, *"cancel"*, *"send"*, *"repeat"*.
  - Configurable providers: Gmail Web, default mail client (`mailto:`), or Microsoft Outlook desktop.
- ⚡ **Instant Quick Commands**:
  - **Open Apps**: Chrome, VS Code, Spotify, Notepad, Calculator, Task Manager, Terminal, etc.
  - **Launch Websites & Search**: Google, YouTube, GitHub, Reddit, Stack Overflow, and direct URL navigation.
  - **Hardware Audio & Brightness**: Volume up/down/set/mute, monitor brightness adjust/set.
  - **System Power**: Workstation lock, sleep, shutdown, and restart with scheduled cancel options.
- 🧠 **Context-Aware Follow-ups**:
  - Remembers recent application & search context (e.g., after searching YouTube, say *"now search for jazz"* or *"scroll down"*).
- 👁️ **Screen Vision & Multimodal Chat**:
  - Instant screen capture (`Ctrl+Shift+S`) analyzed locally via `llava`.
- 📁 **Integrated File Intelligence**:
  - Natural language file search, open, rename, auto-organize, and PDF/DOCX summarization.

---

## 🛠️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│               Electron Frontend (Overlay)             │
│   - Transparent floating window with draggable mascot  │
│   - Collapsible chat panel & quick chips toolbar       │
│   - WebSocket event bridge for real-time voice sync    │
└───────────────────────────▲────────────────────────────┘
                            │ REST / WebSockets
┌───────────────────────────▼────────────────────────────┐
│              Python FastAPI Backend (:8765)            │
│   ├── flows/         - Multi-turn engines, slots & CRM │
│   ├── commands/      - App launch, web, volume, power  │
│   ├── voice/         - openWakeWord, whisper, edge-tts │
│   ├── vision/        - Local Ollama LLaVA integration  │
│   ├── files/         - Search, organize, summarize     │
│   └── memory/        - Conversational session memory   │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Windows)

### Prerequisites

1. **Node.js** (v18+) and **Python** (3.10+)
2. **Ollama** installed and running:
   ```bash
   ollama serve
   ollama pull llama3.2
   ollama pull llava
   ```

### 1. Installation

Clone the repository:
```bash
git clone https://github.com/Yash-Rasal/AURA-Desktop-Assistant.git
cd AURA-Desktop-Assistant
```

Run automated setup:
```powershell
.\scripts\setup.ps1
```

### 2. Launching AURA

Start both the backend API and the Electron companion app with a single command:
```bat
.\start.bat
```

---

## ⌨️ Global Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+A` | Toggle companion window visibility |
| `Ctrl+Shift+S` | Screen capture + vision analysis |
| `Ctrl+Shift+V` | Push-to-talk voice recording |

---

## 🧪 Test Suite

All modules include unit and integration tests that run completely offline without microphone, screen, or cloud dependencies:

```powershell
cd backend
.\.venv\Scripts\pytest -v -p no:faulthandler
```
*(100 tests passing with 100% coverage across control words, normalizers, email flow, context followups, and `/chat` integration).*

---

## 📜 License

This project is open-source and intended for learning, experimentation, and portfolio demonstration.
