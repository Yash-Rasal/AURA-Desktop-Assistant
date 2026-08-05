
import { GoogleGenerativeAI } from "@google/generative-ai";
import { formatFactsForPrompt } from "./persistentMemory";

const genAI = new GoogleGenerativeAI(
  import.meta.env.VITE_GEMINI_API_KEY
);

const model = genAI.getGenerativeModel({
  model: "gemini-2.5-flash",
});

export async function askAuraGemini(message, userFacts = [], signal, recentHistory = []) {
  const memoryText = formatFactsForPrompt(userFacts);

  const systemInstruction = `You are AURA, an intelligent, helpful, and concise AI desktop assistant.
Your name is strictly AURA.

Stored long-term facts about the user:
${memoryText}

Rules:
- Your name is AURA. State clearly that your name is AURA if asked.
- If asked for the user's name or personal facts, check stored memory above. If no fact is stored, state that they haven't told you yet.
- Answer naturally, factually, and concisely in 1 to 3 short sentences suitable for text-to-speech voice playback.
- Avoid markdown symbols like **, *, #, or lists unless explicitly requested.`;

  const history = recentHistory.map((entry) => ({
    role: entry.role === "assistant" ? "model" : "user",
    parts: [{ text: entry.content }],
  }));

  const chatModel = genAI.getGenerativeModel({
    model: "gemini-2.5-flash",
    systemInstruction,
  });

  const chat = chatModel.startChat({ history });

  const result = await chat.sendMessage(message, { signal });
  const responseText = result.response.text();

  return responseText
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/`/g, "")
    .replace(/#+/g, "")
    .replace(/[_~]/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[\u{1F300}-\u{1FAFF}]/gu, "")
    .trim();
}

export async function askGemini(prompt) {
  const result = await model.generateContent(
    "You are AURA, a concise desktop assistant. Answer in 1-3 short sentences. " +
    prompt
  );

  return result.response.text();
}

export async function askGeminiVision(
  prompt,
  imageData
) {
  console.log("Sending image to Gemini");

  const result = await model.generateContent([
    {
      inlineData: {
        data: imageData.split(",")[1],
        mimeType: "image/jpeg",
      },
    },
    {
      text: `
    You are AURA.
    
    Analyze the screenshot and answer the user's question using what is visible on the screen.
    
    Rules:
    - Describe what you actually see.
    - Mention applications, windows, code, errors, websites, or content visible.
    - Do not say "I checked your screen".
    - Do not say "I can see your screen".
    - Answer directly.
    - Maximum 3 sentences.
    
    User request:
    ${prompt}
    `,
    },
  ]);

  console.log("Gemini response received");

  return result.response.text();
}