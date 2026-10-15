const $ = (id) => document.getElementById(id);

const messagesEl = $("messages");
const inputEl = $("input");
const statusEl = $("status");
const previewWrap = $("preview-wrap");
const previewImg = $("screenshot-preview");
const backendUrlInput = $("backend-url");
const speakReplies = $("speak-replies");
const useScreen = $("use-screen");
const btnSend = $("btn-send");
const btnScreenshot = $("btn-screenshot");
const btnVoice = $("btn-voice");
const btnSettings = $("btn-settings");
const btnMinimize = $("btn-minimize");
const btnClearMemory = $("btn-clear-memory");
const settingsPanel = $("settings");

let backendUrl = "http://127.0.0.1:8765";
let mediaRecorder = null;
let audioChunks = [];
let recording = false;
let currentAudio = null;
let activeChatAbort = null;

async function init() {
  if (window.companion?.getBackendUrl) {
    const url = await window.companion.getBackendUrl();
    if (url) {
      backendUrl = url;
      backendUrlInput.value = url;
    }
  }

  backendUrlInput.addEventListener("change", () => {
    backendUrl = backendUrlInput.value.trim() || backendUrl;
  });

  window.companion?.onHotkeyScreenshot?.(() => captureAndAnalyze());
  window.companion?.onHotkeyVoice?.(() => toggleVoice());

  // Connect to WebSocket for voice events
  function connectWebSocket() {
    const ws = new WebSocket(backendUrl.replace("http", "ws") + "/voice/events");
    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "wake") {
        console.log("[Voice] Wake word detected!");
        voiceConversationActive = true;
        setStatus("Listening…");
        btnVoice.classList.add("active");
        
        // Show and focus the companion window
        window.companion?.showWindow?.();
        const panel = document.getElementById("panel");
        if (panel && panel.classList.contains("collapsed")) {
          panel.classList.remove("collapsed");
        }
      } else if (data.type === "transcript") {
        console.log("[Voice] Transcript received:", data.text);
        btnVoice.classList.remove("active");
        if (data.text) {
          inputEl.value = data.text;
          await sendMessage();
        } else {
          console.log("[Voice] No speech detected.");
          setStatus("");
        }
      } else if (data.type === "flow_state") {
        if (data.flow) handleFlowUpdate(data.flow);
      } else if (data.type === "focus_field") {
        inputEl.focus();
      }
    };
    ws.onclose = () => {
      setTimeout(connectWebSocket, 1000); // Reconnect
    };
  }
  connectWebSocket();
  btnSend.addEventListener("click", () => sendMessage());
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    } else if (e.key === "Escape") {
      api("/flow/state")
        .then(res => res.json())
        .then(st => {
          if (st.active) {
            inputEl.value = "cancel";
            sendMessage();
          }
        })
        .catch(() => {});
    }
  });

  const panel = document.getElementById('panel');
  const robotToggle = document.getElementById('robot-toggle');
  
  if (robotToggle && panel) {
    robotToggle.addEventListener('click', () => {
      panel.classList.toggle('collapsed');
    });
  }

  btnScreenshot.addEventListener("click", () => captureAndAnalyze());
  btnVoice.addEventListener("click", () => toggleVoice());
  btnSettings.addEventListener("click", () => settingsPanel.classList.toggle("hidden"));
  btnMinimize.addEventListener("click", () => {
    if (panel) {
      panel.classList.add('collapsed');
    } else {
      window.close();
    }
  });
  btnClearMemory.addEventListener("click", clearMemory);

  const emailProviderSelect = document.getElementById("email-provider");
  if (emailProviderSelect) {
    const saved = localStorage.getItem("email_provider");
    if (saved) emailProviderSelect.value = saved;
    emailProviderSelect.addEventListener("change", () => {
      localStorage.setItem("email_provider", emailProviderSelect.value);
    });
  }

  // Quick Command Chips
  document.querySelectorAll(".quick-chips-bar .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      inputEl.value = chip.dataset.cmd;
      sendMessage();
    });
  });

  // Start robot in idle/resting state
  setStatus("");
  checkHealthLoop();
}

function api(path, options = {}) {
  const url = `${backendUrl.replace(/\/$/, "")}${path}`;
  return fetch(url, options);
}

function setStatus(text) {
  statusEl.textContent = text;
  
  const eyeLeft = document.getElementById('robot-eye-left');
  const eyeRight = document.getElementById('robot-eye-right');
  const cloud = document.getElementById('robot-cloud');
  
  if (cloud) {
    if (text === "Thinking…" || text === "Listening…" || text === "Transcribing…") {
      cloud.textContent = text.replace('…', '...');
      cloud.classList.remove('hidden');
    } else {
      cloud.classList.add('hidden');
    }
  }

  if (!eyeLeft || !eyeRight) return;
  
  eyeLeft.className = 'eye'; // reset
  eyeRight.className = 'eye'; // reset
  
  if (text === "Thinking…" || text === "Transcribing…") {
    eyeLeft.classList.add('thinking');
    eyeRight.classList.add('thinking');
  } else if (text === "Listening…") {
    eyeLeft.classList.add('listening');
    eyeRight.classList.add('listening');
  }
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function getFileIcon(ext) {
  ext = (ext || "").toLowerCase();
  if ([".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt"].includes(ext)) return "📄";
  if ([".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"].includes(ext)) return "🖼️";
  if ([".xlsx", ".xls", ".csv"].includes(ext)) return "📊";
  if ([".pptx", ".ppt"].includes(ext)) return "📽️";
  if ([".zip", ".rar", ".7z", ".tar", ".gz"].includes(ext)) return "📦";
  if ([".exe", ".msi", ".bat", ".cmd"].includes(ext)) return "⚙️";
  if ([".mp3", ".wav", ".flac", ".ogg"].includes(ext)) return "🎵";
  if ([".mp4", ".mkv", ".mov", ".avi"].includes(ext)) return "🎬";
  if ([".py", ".js", ".ts", ".html", ".css", ".json"].includes(ext)) return "💻";
  return "📁";
}

function appendFileCards(matches) {
  if (!matches || matches.length === 0) return;

  const container = document.createElement("div");
  container.className = "file-matches-container";

  matches.forEach((m, idx) => {
    const card = document.createElement("div");
    card.className = `file-card ${idx === 0 ? "is-latest" : ""}`;

    const icon = getFileIcon(m.extension);
    const isDoc = [".pdf", ".docx", ".txt", ".md", ".csv"].includes(m.extension);
    const folderShort = m.folder.split(/[\\/]/).slice(-2).join('/');

    card.innerHTML = `
      <div class="file-header">
        <span class="file-icon">${icon}</span>
        <span class="file-name" title="${m.path}">${m.name}</span>
        ${idx === 0 ? '<span class="badge-latest">Latest</span>' : ''}
      </div>
      <div class="file-meta">
        <span title="${m.folder}">📍 ${folderShort}</span>
        <span>💾 ${m.size}</span>
        <span>🕒 ${m.modified}</span>
      </div>
      <div class="file-actions">
        <button class="file-btn btn-open-folder" title="Highlight in File Explorer">
          📁 Reveal
        </button>
        <button class="file-btn secondary btn-launch-file" title="Open file directly">
          ▶ Open
        </button>
        ${isDoc ? `<button class="file-btn secondary btn-summarize" title="Summarize document">📝 Summarize</button>` : ''}
      </div>
    `;

    card.querySelector(".btn-open-folder").addEventListener("click", async () => {
      try {
        await api("/files/open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: m.path }),
        });
      } catch (e) {
        console.error("Failed to open explorer:", e);
      }
    });

    card.querySelector(".btn-launch-file").addEventListener("click", async () => {
      try {
        await api("/files/launch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: m.path }),
        });
      } catch (e) {
        console.error("Failed to launch file:", e);
      }
    });

    if (isDoc) {
      card.querySelector(".btn-summarize").addEventListener("click", () => {
        inputEl.value = `summarize ${m.name}`;
        sendMessage();
      });
    }

    container.appendChild(card);
  });

  messagesEl.appendChild(container);
  scrollToBottom();
}

function appendQuickCommandCard(cmd) {
  if (!cmd || !cmd.action) return;

  const card = document.createElement("div");
  card.className = "command-card";

  const category = cmd.category || "command";
  const data = cmd.data || {};

  let icon = "⚡";
  let title = "Quick Command";
  let badgeClass = "";
  let badgeText = category.toUpperCase();
  let contentHtml = "";
  let actionsHtml = "";

  if (category === "app") {
    icon = "💻";
    title = data.name || "Application";
    badgeText = "APP LAUNCHED";
    badgeClass = "success";
    actionsHtml = `
      <button class="command-btn btn-relaunch">▶ Launch Again</button>
    `;
  } else if (category === "web") {
    icon = "🌐";
    title = data.title || "Website";
    badgeText = "WEB LAUNCHED";
    badgeClass = "success";
    actionsHtml = `
      <button class="command-btn btn-open-url">🔗 Open Link</button>
    `;
  } else if (category === "hardware") {
    if (cmd.action.startsWith("volume")) {
      const isMuted = data.muted;
      const pct = data.percent !== undefined ? data.percent : 50;
      icon = isMuted ? "🔇" : (pct > 50 ? "🔊" : "🔉");
      title = isMuted ? "Audio Muted" : `Master Volume (${pct}%)`;
      badgeText = isMuted ? "MUTED" : `${pct}%`;
      badgeClass = isMuted ? "danger" : "success";
      contentHtml = `
        <div class="command-meter-wrap">
          <div class="command-meter-track">
            <div class="command-meter-fill" style="width: ${isMuted ? 0 : pct}%;"></div>
          </div>
          <span class="command-meter-label">${isMuted ? 'Muted' : pct + '%'}</span>
        </div>
      `;
      actionsHtml = `
        <button class="command-btn btn-vol-down">🔉 -10%</button>
        <button class="command-btn btn-vol-up">🔊 +10%</button>
        <button class="command-btn ${isMuted ? '' : 'danger'} btn-vol-mute">${isMuted ? '🔈 Unmute' : '🔇 Mute'}</button>
      `;
    } else if (cmd.action.startsWith("brightness")) {
      const pct = data.percent !== undefined ? data.percent : 100;
      icon = pct > 50 ? "☀️" : "🌙";
      title = `Display Brightness (${pct}%)`;
      badgeText = `${pct}%`;
      badgeClass = "success";
      contentHtml = `
        <div class="command-meter-wrap">
          <div class="command-meter-track">
            <div class="command-meter-fill" style="width: ${pct}%;"></div>
          </div>
          <span class="command-meter-label">${pct}%</span>
        </div>
      `;
      actionsHtml = `
        <button class="command-btn btn-bright-down">🌙 -10%</button>
        <button class="command-btn btn-bright-up">☀️ +10%</button>
      `;
    }
  } else if (category === "power") {
    if (cmd.action === "lock") {
      icon = "🔒";
      title = "Workstation Locked";
      badgeText = "SECURITY";
      badgeClass = "success";
    } else if (cmd.action === "sleep") {
      icon = "💤";
      title = "System Suspended";
      badgeText = "POWER";
    } else if (cmd.action === "shutdown") {
      icon = "🛑";
      title = "Shutdown Scheduled";
      badgeText = "WARNING";
      badgeClass = "danger";
      actionsHtml = `<button class="command-btn danger btn-cancel-shutdown">🛑 Cancel Shutdown</button>`;
    } else if (cmd.action === "restart") {
      icon = "🔄";
      title = "Restart Scheduled";
      badgeText = "WARNING";
      badgeClass = "danger";
      actionsHtml = `<button class="command-btn danger btn-cancel-shutdown">🛑 Cancel Restart</button>`;
    } else if (cmd.action === "cancel_shutdown") {
      icon = "✅";
      title = "Shutdown Cancelled";
      badgeText = "CANCELLED";
      badgeClass = "success";
    }
  }

  card.innerHTML = `
    <div class="command-header">
      <div class="command-title">
        <span class="command-icon">${icon}</span>
        <span>${title}</span>
      </div>
      <span class="command-badge ${badgeClass}">${badgeText}</span>
    </div>
    ${contentHtml}
    ${actionsHtml ? `<div class="command-actions">${actionsHtml}</div>` : ""}
  `;

  if (card.querySelector(".btn-relaunch")) {
    card.querySelector(".btn-relaunch").addEventListener("click", () => {
      inputEl.value = `open ${data.name || ''}`;
      sendMessage();
    });
  }
  if (card.querySelector(".btn-open-url") && data.url) {
    card.querySelector(".btn-open-url").addEventListener("click", () => {
      window.companion?.openExternal ? window.companion.openExternal(data.url) : window.open(data.url);
    });
  }
  if (card.querySelector(".btn-vol-up")) {
    card.querySelector(".btn-vol-up").addEventListener("click", () => {
      inputEl.value = "volume up";
      sendMessage();
    });
  }
  if (card.querySelector(".btn-vol-down")) {
    card.querySelector(".btn-vol-down").addEventListener("click", () => {
      inputEl.value = "volume down";
      sendMessage();
    });
  }
  if (card.querySelector(".btn-vol-mute")) {
    card.querySelector(".btn-vol-mute").addEventListener("click", () => {
      inputEl.value = data.muted ? "unmute" : "mute";
      sendMessage();
    });
  }
  if (card.querySelector(".btn-bright-up")) {
    card.querySelector(".btn-bright-up").addEventListener("click", () => {
      inputEl.value = "increase brightness";
      sendMessage();
    });
  }
  if (card.querySelector(".btn-bright-down")) {
    card.querySelector(".btn-bright-down").addEventListener("click", () => {
      inputEl.value = "decrease brightness";
      sendMessage();
    });
  }
  if (card.querySelector(".btn-cancel-shutdown")) {
    card.querySelector(".btn-cancel-shutdown").addEventListener("click", () => {
      inputEl.value = "cancel shutdown";
      sendMessage();
    });
  }

  messagesEl.appendChild(card);
  scrollToBottom();
}

function handleFlowUpdate(flow) {
  if (!flow) return;

  // 1. Auto-expand panel if collapsed
  const panel = document.getElementById("panel");
  if (flow.active && panel && panel.classList.contains("collapsed")) {
    panel.classList.remove("collapsed");
  }

  // 2. Render UI Card
  if (flow.ui_card) {
    appendFlowCard(flow);
  }

  // 3. Dynamic placeholder and input focus
  if (flow.active) {
    if (flow.focus_field === "recipient") {
      inputEl.placeholder = "Type recipient's email (e.g. name@example.com)...";
    } else if (flow.focus_field === "subject") {
      inputEl.placeholder = "Type email subject...";
    } else if (flow.focus_field === "body") {
      inputEl.placeholder = "Type message body... (Say 'done' when finished)";
    } else {
      inputEl.placeholder = "Say or type response... ('cancel' to stop)";
    }
    inputEl.focus();
  } else {
    inputEl.placeholder = "Awaiting input... (Say 'Hey Jarvis' or click 🎤)";
  }
}

function appendFlowCard(flow) {
  if (!flow || !flow.ui_card) return;
  const cardData = flow.ui_card;
  const card = document.createElement("div");
  card.className = "command-card flow-card";

  const title = cardData.title || "Guided Flow";
  const stepLabel = flow.step_label || cardData.step_label || "";
  const slots = cardData.slots || {};

  let slotsHtml = '<div class="flow-slots-grid">';
  for (const [key, val] of Object.entries(slots)) {
    if (val !== undefined && val !== null && val !== "") {
      const displayVal = String(val).length > 80 ? String(val).slice(0, 80) + "…" : String(val);
      slotsHtml += `
        <div class="flow-slot-item">
          <span class="flow-slot-label">${key.toUpperCase()}:</span>
          <span class="flow-slot-val">${displayVal}</span>
        </div>
      `;
    }
  }
  slotsHtml += "</div>";

  let actionsHtml = "";
  if (cardData.actions && cardData.actions.length > 0) {
    actionsHtml = '<div class="command-actions flow-actions">';
    for (const act of cardData.actions) {
      const cls = act.danger ? "command-btn danger" : (act.primary ? "command-btn primary-btn" : "command-btn");
      actionsHtml += `<button class="${cls}" data-cmd="${act.cmd}">${act.label}</button>`;
    }
    actionsHtml += "</div>";
  }

  card.innerHTML = `
    <div class="command-header">
      <div class="command-title">
        <span class="command-icon">✉️</span>
        <span>${title}</span>
      </div>
      <span class="command-badge">${stepLabel}</span>
    </div>
    ${slotsHtml}
    ${actionsHtml}
  `;

  card.querySelectorAll(".flow-actions button").forEach(btn => {
    btn.addEventListener("click", () => {
      inputEl.value = btn.dataset.cmd;
      sendMessage();
    });
  });

  messagesEl.appendChild(card);
  scrollToBottom();
}

async function checkHealthLoop() {
  let backendAnnounced = false;
  let ollamaAnnounced = false;
  let ollamaRetries = 0;

  while (true) {
    try {
      const res = await api("/health");
      if (res.ok) {
        const data = await res.json();
        if (data.ollama?.ok) {
          if (statusEl.textContent !== "Listening…" && statusEl.textContent !== "Thinking…") {
            setStatus(""); // idle — ready
          }
          if (ollamaAnnounced) {
            appendMessage("system", "Ollama connected and ready.");
          }
          break;
        } else {
          ollamaRetries++;
          if (ollamaRetries >= 4 && !ollamaAnnounced) {
            appendMessage(
              "system",
              "Ollama not detected. Run: ollama serve — then: ollama pull llama3.2 && ollama pull llava"
            );
            if (statusEl.textContent !== "Listening…" && statusEl.textContent !== "Thinking…") {
              setStatus("Ollama offline");
            }
            ollamaAnnounced = true;
          }
        }
      }
    } catch {
      if (!backendAnnounced) {
        appendMessage("system", "Backend starting… wait a few seconds.");
        backendAnnounced = true;
      }
    }
    await new Promise(r => setTimeout(r, 2000));
  }
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  // Cancel any prior pending request and stop currently playing audio
  if (activeChatAbort) {
    activeChatAbort.abort();
    activeChatAbort = null;
  }
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }

  const controller = new AbortController();
  activeChatAbort = controller;

  inputEl.value = "";
  appendMessage("user", text);
  btnSend.disabled = true;
  setStatus("Thinking…");

  try {
    const res = await api("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, use_screen: useScreen.checked }),
      signal: controller.signal,
    });
    
    let data;
    try { data = await res.json(); } catch { data = { detail: await res.text() }; }
    if (!res.ok) throw new Error(data.detail || "Chat failed");

    // If this request was superseded while waiting, don't display or speak stale reply
    if (controller.signal.aborted) return;

    appendMessage("assistant", data.reply);
    if (data.file_action && data.file_action.action === "find_files" && data.file_action.data?.matches?.length > 0) {
      appendFileCards(data.file_action.data.matches);
    }
    if (data.quick_command) {
      appendQuickCommandCard(data.quick_command);
    }
    if (data.flow) {
      handleFlowUpdate(data.flow);
    }
    if (speakReplies.checked) {
      await playSpeech(data.reply);
    }
  } catch (err) {
    if (err.name === "AbortError" || controller.signal.aborted) {
      console.log("[Chat] Request cancelled by newer query.");
      return;
    }
    appendMessage("system", String(err.message || err));
  } finally {
    if (activeChatAbort === controller) {
      activeChatAbort = null;
      btnSend.disabled = false;
      setStatus(""); // return to idle
    }
  }
}

async function captureAndAnalyze() {
  const question = inputEl.value.trim() || "What do you see? How can you help with what's on screen?";
  appendMessage("user", `📷 ${question}`);
  btnScreenshot.disabled = true;
  setStatus("Capturing…");

  try {
    const shotRes = await api("/screenshot", { method: "POST" });
    let shot;
    try { shot = await shotRes.json(); } catch { shot = { detail: await shotRes.text() }; }
    if (!shotRes.ok) throw new Error(shot.detail || "Screenshot failed");

    if (shot.preview) {
      previewImg.src = shot.preview;
      previewWrap.classList.remove("hidden");
    }

    setStatus("Analyzing screen…");
    const res = await api("/vision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, capture: false }),
    });
    
    let data;
    try { data = await res.json(); } catch { data = { detail: await res.text() }; }
    if (!res.ok) throw new Error(data.detail || "Vision failed");

    inputEl.value = "";
    appendMessage("assistant", data.reply);
    if (speakReplies.checked) {
      await playSpeech(data.reply);
    }
  } catch (err) {
    appendMessage("system", String(err.message || err));
  } finally {
    btnScreenshot.disabled = false;
    setStatus("Ready");
  }
}

async function toggleVoice() {
  // If we are idle, trigger a manual wake
  if (!btnVoice.classList.contains("active")) {
    try { await fetch(`${backendUrl}/voice/trigger`, { method: "POST" }); } catch (e) {}
  }
}



async function playSpeech(text) {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  try {
    const res = await api("/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 2000) }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    currentAudio = new Audio(url);
    // Wait for audio to finish playing before returning
    await new Promise((resolve) => {
      currentAudio.onended = resolve;
      currentAudio.onerror = resolve;
      currentAudio.play().catch(resolve);
    });
  } catch (err) {
    appendMessage("system", "TTS Error: " + err.message);
  } finally {
    // Always unmute voice loop on backend once speech finishes or fails
    try { await fetch(`${backendUrl}/voice/unmute`, { method: "POST" }); } catch (e) {}
  }
}

async function clearMemory() {
  try {
    await api("/memory/clear", { method: "POST" });
    messagesEl.innerHTML = "";
    previewWrap.classList.add("hidden");
    appendMessage("system", "Session cleared.");
  } catch (err) {
    appendMessage("system", String(err.message || err));
  }
}

init();
