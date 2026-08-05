export function createRecognition() {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      return null;
    }
  
    const recognition = new SpeechRecognition();
  
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
  
    return recognition;
  }
