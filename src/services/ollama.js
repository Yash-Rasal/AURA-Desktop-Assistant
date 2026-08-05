
// --- Ollama.js

import { formatFactsForPrompt } from "./persistentMemory";

const OLLAMA_KEEP_ALIVE = "90s";

export async function fetchOllama(endpoint, options) {
  const primaryUrl =
    typeof window.__TAURI_INTERNALS__ !== "undefined"
      ? "http://localhost:11434"
      : "/ollama";

  const urls = [...new Set([primaryUrl, "http://localhost:11434", "/ollama"])];

  let lastError = null;
  for (const baseUrl of urls) {
    try {
      const res = await fetch(`${baseUrl}${endpoint}`, options);
      if (res.ok) {
        return res;
      }
      lastError = new Error(`Ollama returned ${res.status}: ${res.statusText}`);
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error("Failed to connect to Ollama");
}

function formatRecentConversation(history) {
  if (history.length === 0) {
    return "";
  }

  const lines = history.map(
    (entry) => `${entry.role.toUpperCase()}: ${entry.content}`,
  );

  return `
      Recent conversation:
      ${lines.join("\n      ")}
`;
}

export async function askAura(message, userFacts = [], signal, recentHistory = []) {
  const memoryText = formatFactsForPrompt(userFacts);

  const systemPrompt = `[IDENTITY OVERRIDE]
You are strictly AURA, an intelligent AI desktop assistant.
You are NOT Gemma, and you must NEVER state that you are Gemma, trained by Google, or created by DeepMind.

Stored long-term facts about the user:
${memoryText}

Rules:
- If asked "who are you" or "what is your name", state clearly that you are AURA.
- Never refer to yourself as Gemma, LLM, or Google assistant.
- If asked for details about the user, check the stored facts above.
  - If a fact/name is listed, use it.
  - If no fact exists in memory, state that the user hasn't told you yet.
- Be concise, direct, and factually accurate.`;

  const messages = [
    { role: "system", content: systemPrompt },
    ...recentHistory.map((entry) => ({
      role: entry.role,
      content: entry.content,
    })),
    { role: "user", content: message },
  ];

  const response = await fetchOllama("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gemma3:1b",
      messages,
      stream: false,
      keep_alive: OLLAMA_KEEP_ALIVE,
    }),
    signal,
  });

  const data = await response.json();
  const rawReply = data.message?.content || data.response || "";

  let reply = rawReply
    .replace(/\b(gemma|gemma\s*3|gemma\s*2)\b/gi, "AURA")
    .replace(/\b(google\s*deepmind|google)\b/gi, "AURA")
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/`/g, "")
    .replace(/#+/g, "")
    .replace(/[_~]/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[\u{1F300}-\u{1FAFF}]/gu, "")
    .trim();

  return reply;
}

