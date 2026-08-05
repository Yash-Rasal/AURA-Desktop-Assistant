import { saveFacts } from "./persistentMemory";
import { fetchOllama } from "./ollama";

const OLLAMA_KEEP_ALIVE = "90s";
const EXTRACTION_MODEL = "gemma3:1b";


const VALID_CATEGORIES = new Set([
  "name",
  "location",
  "profession",
  "preference",
  "hobby",
  "project",
  "goal",
  "deadline",
]);

const GREETING_PATTERN =
  /^(hi|hello|hey|thanks|thank you|ok|okay|bye|goodbye|good morning|good night)[!.?\s]*$/i;

const TRANSIENT_PATTERNS = [
  /^open\s+/i,
  /\b(weather|temperature|forecast)\b/i,
  /\b(what time|what's the time|current time)\b/i,
  /\b(what date|today's date)\b/i,
  /\b(set a timer|set an alarm|remind me in \d+)\b/i,
  /\b(play music|pause|volume up|volume down|mute)\b/i,
  /\b(check my screen|what is on my screen|what's on my screen)\b/i,
  /\b(stop listening|go to sleep|stop aura)\b/i,
];

const PERSONAL_HINTS = [
  /\bmy name is\b/i,
  /\bi am\b/i,
  /\bi'm\b/i,
  /\bi live in\b/i,
  /\bi work (as|at|on|for)\b/i,
  /\bmy job\b/i,
  /\bmy profession\b/i,
  /\bi (like|love|prefer|enjoy|hate|dislike)\b/i,
  /\bmy (hobby|hobbies|project|goal|deadline|birthday)\b/i,
  /\bi'm (working on|building|learning|studying)\b/i,
  /\b(call me|from|based in|located in)\b/i,
  /\bremember (that|this)\b/i,
  /\bforgot to tell you\b/i,
];

export function isTransientMessage(text) {
  const trimmed = text.trim();

  if (!trimmed) {
    return true;
  }

  if (GREETING_PATTERN.test(trimmed)) {
    return true;
  }

  return TRANSIENT_PATTERNS.some((pattern) => pattern.test(trimmed));
}

export function shouldExtractMemory(text) {
  const trimmed = text.trim();

  if (!trimmed || isTransientMessage(trimmed)) {
    return false;
  }

  if (PERSONAL_HINTS.some((pattern) => pattern.test(trimmed))) {
    return true;
  }

  const words = trimmed.split(/\s+/);

  if (words.length < 5) {
    return false;
  }

  if (/^(what|how|when|where|why|who|can you|could you|tell me|explain)\b/i.test(trimmed)) {
    return false;
  }

  return true;
}

function parseExtractedFacts(raw) {
  try {
    const data = JSON.parse(raw);
    const rawFacts = Array.isArray(data) ? data : (data.facts || []);

    const facts = [];
    for (const item of rawFacts) {
      if (!item || typeof item !== "object") {
        continue;
      }

      const category = String(item.category || "").trim().toLowerCase();
      const fact = String(item.fact || "").trim();

      if (VALID_CATEGORIES.has(category) && fact.length >= 2) {
        facts.push({ category, fact });
      }
    }
    return facts;
  } catch (e) {
    console.error("Failed to parse extracted JSON facts from Ollama:", e, raw);
    return [];
  }
}

async function callOllama(prompt, signal) {
  const response = await fetchOllama("/api/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: EXTRACTION_MODEL,
      prompt,
      stream: false,
      format: "json",
      keep_alive: OLLAMA_KEEP_ALIVE,
    }),
    signal,
  });

  const data = await response.json();
  return data.response?.trim() ?? "";
}

export async function extractFacts(text, signal) {
  const prompt = `You are a memory extraction assistant.
Extract durable personal details about the user from their message.

Valid categories are: name, location, profession, preference, hobby, project, goal, deadline

Only extract real, durable facts. Do NOT extract small talk, greetings, temporary tasks or commands like "open website".

Format the response as a JSON array of objects with "category" and "fact" keys.
If no facts should be stored, return an empty array: []

Examples:
User: "My name is Yash and I live in Mumbai."
[
  {"category": "name", "fact": "Yash"},
  {"category": "location", "fact": "Mumbai"}
]

User: "I'm learning Rust for a side project due next month."
[
  {"category": "project", "fact": "Learning Rust for a side project"},
  {"category": "deadline", "fact": "Side project due next month"}
]

User: "Open Chrome."
[]

User: "${text}"
`;

  const raw = await callOllama(prompt, signal);
  return parseExtractedFacts(raw);
}

export async function processMessageForMemory(text, signal) {
  if (!shouldExtractMemory(text)) {
    return [];
  }

  const facts = await extractFacts(text, signal);

  if (facts.length === 0) {
    return [];
  }

  await saveFacts(facts);
  return facts;
}
