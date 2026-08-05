import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { invoke } from "@tauri-apps/api/core";
import { handleOpenApp, handleOpenUrl } from "./services/appCommands";
import { followUpListening } from "./services/followUpListening";
import { createRecognition } from "./services/speechRecognition";
import { clearConversation, resetAfterError } from "./services/speechResponses";
import { speak, stopSpeaking } from "./services/speechSynthesis";
import {
  startWakeWordListener,
  stopWakeWordListener,
} from "./services/wakeWordListener";

const ORB_LABELS = {
  idle: "AURA",
  wake: "👂",
  listening: "🎤",
  thinking: "...",
  speaking: "✦",
};

function App() {
  const [state, setState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef(null);
  const followUpTimerRef = useRef(null);
  const followUpStartTimerRef = useRef(null);
  const listeningModeRef = useRef(false);
  const interactionActiveRef = useRef(false);
  const requestActiveRef = useRef(false);
  const requestControllerRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const mountedRef = useRef(false);

  if (!recognitionRef.current) {
    recognitionRef.current = createRecognition();
  }

  const stopFollowUpTimers = useCallback(() => {
    clearTimeout(followUpTimerRef.current);
    clearTimeout(followUpStartTimerRef.current);
    clearTimeout(silenceTimerRef.current);
    followUpTimerRef.current = null;
    followUpStartTimerRef.current = null;
    silenceTimerRef.current = null;
  }, []);

  const startFollowUpListening = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }

    const started = followUpListening(
      recognitionRef,
      followUpTimerRef,
      listeningModeRef,
      setState,
    );

    interactionActiveRef.current = started;
  }, []);

  const submitVoiceRequest = useCallback(
    async (text) => {
      if (requestActiveRef.current || !mountedRef.current || !text) {
        return;
      }

      requestActiveRef.current = true;
      const requestController = new AbortController();
      requestControllerRef.current = requestController;
      clearTimeout(followUpTimerRef.current);
      clearTimeout(silenceTimerRef.current);
      followUpTimerRef.current = null;
      silenceTimerRef.current = null;
      setTranscript(text);
      setState("thinking");

      try {
        const { routeRequest } = await import("./services/assistantRouter");
        const reply = await routeRequest(text, requestController.signal);

        if (!mountedRef.current) {
          return;
        }

        if (typeof reply === "object" && reply.type === "open_url") {
          setState("speaking");
          await handleOpenUrl(reply, invoke, speak, startFollowUpListening);
          return;
        }

        if (typeof reply === "object" && reply.type === "open_app") {
          setState("speaking");
          await handleOpenApp(reply, invoke, speak, startFollowUpListening);
          return;
        }

        if (reply === "__STOP_LISTENING__") {
          listeningModeRef.current = false;
          interactionActiveRef.current = false;
          stopFollowUpTimers();
          setState("idle");
          speak("Going to sleep.");
          return;
        }

        setState("speaking");
        speak(String(reply), () => {
          if (!mountedRef.current) {
            return;
          }

          clearConversation(setTranscript, () => {
            clearTimeout(followUpStartTimerRef.current);
            followUpStartTimerRef.current = setTimeout(() => {
              followUpStartTimerRef.current = null;
              startFollowUpListening();
            }, 1000);
          });
        });
      } catch (error) {
        console.error("Unable to complete the voice request:", error);

        if (!mountedRef.current) {
          return;
        }

        let errorMessage = "Sorry, I couldn't complete that request.";
        if (
          error?.message?.toLowerCase().includes("ollama") ||
          error?.message?.toLowerCase().includes("fetch") ||
          error?.message?.toLowerCase().includes("failed")
        ) {
          errorMessage =
            "Sorry, I couldn't connect to Ollama. Please make sure Ollama is running.";
        }

        setState("speaking");
        speak(errorMessage, () => {
          if (mountedRef.current) {
            interactionActiveRef.current = false;
            resetAfterError(setState, setTranscript);
          }
        });
      } finally {
        requestActiveRef.current = false;
        if (requestControllerRef.current === requestController) {
          requestControllerRef.current = null;
        }
      }
    },
    [startFollowUpListening, stopFollowUpTimers],
  );

  // ── Lifecycle cleanup ────────────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      interactionActiveRef.current = false;
      requestActiveRef.current = false;
      requestControllerRef.current?.abort();
      requestControllerRef.current = null;
      clearTimeout(silenceTimerRef.current);
      stopFollowUpTimers();
      stopSpeaking();
      stopWakeWordListener();

      try {
        recognitionRef.current?.abort();
      } catch {
        // The recognition session may already be stopped.
      }
    };
  }, [stopFollowUpTimers]);

  // ── Wake-word listener ───────────────────────────────────────────────────────
  // Run a lightweight background listener while AURA is idle.
  // The moment the user says "Hey Aura" (or a variant), we flash the wake
  // state for 300 ms and then start the main recognition session.
  const startListeningCoreRef = useRef(null); // forward-ref so the effect can call it

  useEffect(() => {
    if (state === "idle") {
      startWakeWordListener(() => {
        if (!mountedRef.current) return;
        setState("wake");
        setTimeout(() => {
          if (mountedRef.current) startListeningCoreRef.current?.();
        }, 300);
      });
    } else {
      stopWakeWordListener();
    }

    return () => {
      stopWakeWordListener();
    };
  }, [state]);

  // ── Main recognition events ──────────────────────────────────────────────────
  useEffect(() => {
    const recognition = recognitionRef.current;

    if (!recognition) {
      return undefined;
    }

    recognition.onstart = () => {
      if (mountedRef.current) {
        setState("listening");
      }
    };

    recognition.onresult = (event) => {
      if (requestActiveRef.current || !mountedRef.current) {
        return;
      }

      let text = "";
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      text = text.trim();

      if (!text) {
        return;
      }

      setTranscript(text);
      clearTimeout(silenceTimerRef.current);

      // Debounce: wait for 1.6s of silence before completing utterance
      silenceTimerRef.current = setTimeout(() => {
        if (!requestActiveRef.current && mountedRef.current) {
          try {
            recognition.stop();
          } catch {
            // Already stopped
          }
          submitVoiceRequest(text);
        }
      }, 1600);
    };

    recognition.onerror = (error) => {
      console.warn("Speech recognition error:", error.error);
      listeningModeRef.current = false;
      interactionActiveRef.current = false;
      clearTimeout(followUpTimerRef.current);
      clearTimeout(silenceTimerRef.current);
      followUpTimerRef.current = null;
      silenceTimerRef.current = null;

      if (mountedRef.current) {
        setState("idle");
      }
    };

    recognition.onend = () => {
      if (!mountedRef.current || requestActiveRef.current) {
        return;
      }

      setState((currentState) => {
        if (currentState === "listening" || currentState === "idle" || currentState === "wake") {
          interactionActiveRef.current = false;
          return "idle";
        }

        return currentState;
      });
    };

    return () => {
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
    };
  }, [startFollowUpListening, stopFollowUpTimers]);

  // ── Core listening starter (used by both click and wake word) ───────────────
  const startListeningCore = useCallback(() => {
    const recognition = recognitionRef.current;

    if (interactionActiveRef.current || requestActiveRef.current) {
      return;
    }

    if (!recognition) {
      setTranscript(
        "Speech recognition is not available in this version of Windows WebView.",
      );
      setState("idle");
      return;
    }

    stopFollowUpTimers();
    setTranscript("");
    interactionActiveRef.current = true;

    try {
      recognition.start();
    } catch (error) {
      console.warn("Unable to start speech recognition:", error);
      interactionActiveRef.current = false;
      setState("idle");
    }
  }, [stopFollowUpTimers]);

  // Keep the forward ref up to date.
  startListeningCoreRef.current = startListeningCore;

  // Public click handler – stops wake listener then starts main recognition.
  const startListening = useCallback(() => {
    stopWakeWordListener();
    startListeningCore();
  }, [startListeningCore]);

  return (
    <div className="aura-app">
      {transcript && (
        <div className="aura-transcript">
          {transcript}
          <div className="aura-transcript-tail" />
        </div>
      )}

      <div data-tauri-drag-region className="aura-drag-region">
        <button
          type="button"
          className={`aura-orb aura-orb--${state}`}
          onClick={startListening}
          aria-label="Start listening"
          title={state === "wake" ? 'Listening for "Hey Aura"' : "Click to speak"}
        >
          {ORB_LABELS[state]}
        </button>
      </div>
    </div>
  );
}

export default App;
