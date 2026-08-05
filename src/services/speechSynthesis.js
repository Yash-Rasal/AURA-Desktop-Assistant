let activeSpeech = null;
let voices = [];

function loadVoices() {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    voices = window.speechSynthesis.getVoices();
  }
}

// WebView2 loaded voices asynchronously. This event listener triggers when voices populate.
if (typeof window !== "undefined" && window.speechSynthesis) {
  loadVoices();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }
}

export function speak(text, onEnd) {
  const speech = new SpeechSynthesisUtterance(text);
  
  if (voices.length === 0) {
    loadVoices();
  }

  // Fallback pattern to locate preferred voice or general english alternatives
  const preferredVoice = voices.find(
    (voice) =>
      voice.name === "Microsoft Ravi - English (India)" ||
      voice.name.includes("Ravi") ||
      voice.lang === "en-IN" ||
      voice.lang.startsWith("en-")
  );

  if (preferredVoice) {
    speech.voice = preferredVoice;
  }

  speech.rate = 1.05; // Slightly faster for responsiveness
  speech.pitch = 1;
  speech.onend = () => {
    if (activeSpeech === speech) {
      activeSpeech = null;
      onEnd?.();
    }
  };
  speech.onerror = speech.onend;

  activeSpeech = speech;
  
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(speech);
  } else {
    // If speech synthesis is completely unavailable
    onEnd?.();
  }
}

export function stopSpeaking() {
  activeSpeech = null;
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
