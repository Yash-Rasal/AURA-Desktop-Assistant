
// ---- assistantRouter.js

import { isSleepCommand, isScreenCommand } from "./voiceCommands";

const WEBSITES = Object.freeze({
  youtube: "https://youtube.com",
  google: "https://google.com",
  github: "https://github.com",
  chatgpt: "https://chatgpt.com",
  gmail: "https://mail.google.com",
  amazon: "https://amazon.in",
  netflix: "https://netflix.com",
  linkedin: "https://linkedin.com",
  reddit: "https://reddit.com",
});

export async function routeRequest(text, signal) {
  const lower = text.toLowerCase();
  const wantsScreen = isScreenCommand(text);

  if (lower.startsWith("open ")) {
    const target = text
      .replace(/^open\s+/i, "")
      .trim()
      .toLowerCase()
      .replace(/[.,!?]+$/g, "");
  
    if (WEBSITES[target]) {
      return {
        type: "open_url",
        url: WEBSITES[target],
      };
    }
  
    return {
      type: "open_app",
      app: target,
    };
  }

  if (isSleepCommand(text)) {
    return "__STOP_LISTENING__";
  }

  if (wantsScreen) {
    const [{ captureScreen }, { askGeminiVision }] = await Promise.all([
      import("./screenCapture"),
      import("./gemini"),
    ]);
    const image = await captureScreen();
    return askGeminiVision(text, image);
  }

  const [{ askAura }, { askAuraGemini }, { addMessage, getConversationHistory }, { loadUserFacts }, { processMessageForMemory }] =
    await Promise.all([
      import("./ollama"),
      import("./gemini"),
      import("./conversationMemory"),
      import("./persistentMemory"),
      import("./intelligentMemory"),
    ]);
  let userFacts = [];
  try {
    userFacts = await loadUserFacts();
  } catch (err) {
    console.warn("Unable to load user facts:", err);
  }
  const recentHistory = getConversationHistory();

  let reply;
  try {
    reply = await askAuraGemini(text, userFacts, signal, recentHistory);
  } catch (geminiError) {
    console.warn("Gemini API error, falling back to local Ollama:", geminiError);
    reply = await askAura(text, userFacts, signal, recentHistory);
  }

  processMessageForMemory(text, signal).catch((error) => {
    console.warn("Memory extraction failed:", error);
  });

  addMessage("user", text);
  addMessage("assistant", reply);
  return reply;
}
