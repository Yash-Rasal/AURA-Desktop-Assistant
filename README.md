# AURA - AI Desktop Assistant

AURA (AI Universal Response Assistant) is a desktop AI assistant built with **React**, **Tauri**, **Ollama**, and **Google Gemini Vision**. It combines local LLM inference with cloud-based vision capabilities to provide a lightweight, privacy-focused desktop assistant through a floating overlay interface.

---

## Features

- 💬 Local AI conversations using Ollama
- 👁️ Screen understanding with Gemini Vision API
- 🎤 Voice input using Speech Recognition
- 🔊 Text-to-Speech responses
- 🖥️ Floating desktop assistant overlay
- 🧠 Conversation memory for contextual responses
- 📸 Screen capture and analysis
- ⚡ Hybrid AI routing (Local + Cloud)
- 🖱️ Draggable always-on-top assistant

---

## Tech Stack

### Frontend
- React
- Vite
- JavaScript

### Desktop
- Tauri
- Rust

### AI
- Ollama
- Gemma 3 (Local LLM)
- Google Gemini Vision API

### Web APIs
- SpeechRecognition API
- SpeechSynthesis API
- Screen Capture API

---

## Project Structure

```
src/
 ├── components/
 ├── services/
 ├── assets/
 └── App.jsx

src-tauri/
 ├── src/
 └── tauri.conf.json
```

---

## Installation

### Clone the repository

```bash
git clone https://github.com/Yash-Rasal/AURA-Desktop-Assistant.git
```

```bash
cd AURA-Desktop-Assistant
```

### Install dependencies

```bash
npm install
```

### Configure environment variables

Create a `.env` file.

```env
VITE_GEMINI_API_KEY=YOUR_API_KEY
```

### Install Ollama

Download and install Ollama.

Pull the required model:

```bash
ollama pull gemma3:1b
```

Start the Ollama server.

---

## Run the project

```bash
npm run tauri dev
```

---

## Screenshots

> Screenshots and demo GIF will be added soon.

---

## Future Improvements

- Multi-agent workflows
- Better memory management
- Plugin architecture
- OCR support
- Local vision model support
- Automation tools
- Cross-platform support

---

## License

This project is intended for learning and portfolio purposes.
