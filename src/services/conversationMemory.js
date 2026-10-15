
// --- conversationMemory.js

const STORAGE_KEY = "aura_conversation_history";

function loadHistory() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Ignore storage errors
  }
}

const conversationHistory = loadHistory();

export function addMessage(role, content) {
  conversationHistory.push({
    role,
    content,
  });

  // Keep last 20 messages (10 conversation turns)
  if (conversationHistory.length > 20) {
    conversationHistory.shift();
  }

  saveHistory(conversationHistory);
}

export function getConversationHistory() {
  return conversationHistory;
}

export function clearConversationHistory() {
  conversationHistory.length = 0;
  saveHistory(conversationHistory);
}