// --- wakeWordListener.js
//
// Runs a separate, lightweight SpeechRecognition session that continuously
// listens for the wake word. As soon as the phrase is heard with sufficient
// confidence, the callback fires and the listener stops so the main
// recognition can take over.

const WAKE_PHRASES = [
  "aura",
  "ora",
  "hey aura",
  "hey ora",
  "hi aura",
  "hello aura",
  "ok aura",
  "okay aura",
  "aura wake up",
  "wake up aura",
  "wake up",
];

// Minimum recognition confidence required to accept a wake-word match.
const MIN_CONFIDENCE = 0.3;

let wakeRecognition = null;
let active = false;
let restartTimer = null;
let startupTimer = null;

/**
 * Start the background wake-word listener.
 * @param {() => void} onWakeWord Called when the wake phrase is detected.
 */
export function startWakeWordListener(onWakeWord) {
  // Clean up any existing session or pending timers first
  stopWakeWordListener();

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) return;

  active = true;

  function startSession() {
    if (!active) return;

    try {
      wakeRecognition = new SpeechRecognition();
      wakeRecognition.continuous = true;
      wakeRecognition.interimResults = true;
      wakeRecognition.lang = "en-US";
      wakeRecognition.maxAlternatives = 5;

      wakeRecognition.onresult = (event) => {
        if (!active) return;

        for (let i = event.resultIndex; i < event.results.length; i++) {
          for (let j = 0; j < event.results[i].length; j++) {
            const rawTranscript = event.results[i][j].transcript || "";
            const rawConfidence = event.results[i][j].confidence;

            // Chromium Web Speech API often returns confidence 0 or undefined.
            // Treat 0, null, or undefined as valid (1.0).
            const confidence =
              rawConfidence === 0 ||
              rawConfidence === undefined ||
              rawConfidence === null
                ? 1
                : rawConfidence;

            if (confidence < MIN_CONFIDENCE) continue;

            // Clean transcript by converting to lowercase and stripping punctuation
            const heardClean = rawTranscript
              .toLowerCase()
              .replace(/[^\w\s]/g, "")
              .replace(/\s+/g, " ")
              .trim();

            if (!heardClean) continue;

            const matched = WAKE_PHRASES.some((phrase) => {
              const p = phrase.toLowerCase().trim();
              return (
                heardClean === p ||
                heardClean.startsWith(p + " ") ||
                heardClean.endsWith(" " + p) ||
                heardClean.includes(" " + p + " ")
              );
            });

            if (matched) {
              // Immediately stop listening & abort to free the microphone stream
              active = false;
              clearTimeout(restartTimer);
              clearTimeout(startupTimer);
              restartTimer = null;
              startupTimer = null;

              if (wakeRecognition) {
                try {
                  wakeRecognition.onresult = null;
                  wakeRecognition.onend = null;
                  wakeRecognition.onerror = null;
                  wakeRecognition.abort();
                } catch {
                  // Ignore abort errors
                }
                wakeRecognition = null;
              }

              onWakeWord();
              return;
            }
          }
        }
      };

      wakeRecognition.onend = () => {
        if (!active) return;
        clearTimeout(restartTimer);
        restartTimer = setTimeout(startSession, 150);
      };

      wakeRecognition.onerror = (e) => {
        if (!active) return;
        if (e.error === "aborted" || e.error === "no-speech") {
          return;
        }
        // Back off longer if the microphone permission was denied
        const delay =
          e.error === "not-allowed" || e.error === "service-not-allowed"
            ? 5000
            : 300;
        clearTimeout(restartTimer);
        restartTimer = setTimeout(startSession, delay);
      };

      wakeRecognition.start();
    } catch {
      if (active) {
        clearTimeout(restartTimer);
        restartTimer = setTimeout(startSession, 500);
      }
    }
  }

  // Short delay to allow the audio pipeline to stabilize
  startupTimer = setTimeout(startSession, 200);
}

/** Stop the background wake-word listener. */
export function stopWakeWordListener() {
  active = false;

  clearTimeout(startupTimer);
  clearTimeout(restartTimer);
  startupTimer = null;
  restartTimer = null;

  if (wakeRecognition) {
    try {
      wakeRecognition.onresult = null;
      wakeRecognition.onend = null;
      wakeRecognition.onerror = null;
      wakeRecognition.abort();
    } catch {
      // Already stopped – ignore.
    }
    wakeRecognition = null;
  }
}

/** Returns true while the listener is running. */
export function isWakeWordListenerActive() {
  return active;
}

