import collections
from pathlib import Path
import queue
import threading
import time
import numpy as np
import sounddevice as sd
from config import settings
from voice.stt import _get_model

# Constants
SR = 16000
FRAME = 1280          # openWakeWord expects 80 ms frames at 16kHz (1280 samples)
MAX_SEC = 15.0        # maximum recording time

events = queue.Queue() # Drains into WebSocket
is_muted = False       # Set to True when TTS is playing
manual_trigger = False # Set to True to force wake
_mute_timer = None

def _auto_unmute():
    global is_muted, _mute_timer
    if is_muted:
        print("[VoiceLoop] Safety watchdog: Auto-unmuting voice loop.", flush=True)
        is_muted = False
    _mute_timer = None

def set_muted(muted: bool, timeout_sec: float = 40.0):
    global is_muted, _mute_timer
    is_muted = muted
    if _mute_timer:
        try:
            _mute_timer.cancel()
        except Exception:
            pass
        _mute_timer = None
    if muted:
        _mute_timer = threading.Timer(timeout_sec, _auto_unmute)
        _mute_timer.daemon = True
        _mute_timer.start()

def force_trigger():
    global manual_trigger
    manual_trigger = True

def _run_loop():
    from openwakeword.model import Model

    models = getattr(settings, "wakeword_models", ["hey_jarvis", "alexa"])
    threshold = float(getattr(settings, "wakeword_threshold", 0.45))

    print(f"[VoiceLoop] Loading OpenWakeWord models {models} (threshold={threshold})...", flush=True)
    oww = Model(wakeword_models=models)

    state = "WAIT"
    buf = []
    preroll = collections.deque(maxlen=4)  # ~320ms buffer to preserve speech onset
    speech_detected = False
    consecutive_quiet = 0

    print("[VoiceLoop] Initializing microphone stream...", flush=True)

    with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=FRAME) as stream:
        # Brief baseline ambient noise calibration (~0.5s)
        ambient_samples = []
        for _ in range(6):
            cal_frame, _ = stream.read(FRAME)
            ambient_samples.append(np.abs(cal_frame[:, 0]).mean())
        ambient_mean = float(np.mean(ambient_samples)) if ambient_samples else 10.0
        # Speech threshold: sensitive to natural conversational voice (at least 45, or 2.8x ambient)
        speech_threshold = max(45.0, ambient_mean * 2.8)
        clean_names = [Path(m).stem.replace("_v0.1", "").replace("_", " ").title() for m in models]
        print(f"[VoiceLoop] Ready! Say {' or '.join(repr(name) for name in clean_names)} to activate.", flush=True)

        global manual_trigger

        while True:
            frame, _ = stream.read(FRAME)

            if is_muted:
                continue # ignore audio while robot is speaking

            pcm = frame[:, 0]

            if state == "WAIT":
                preroll.append(pcm)
                scores = oww.predict(pcm)
                max_score = max(scores.values()) if scores else 0.0

                if manual_trigger or max_score > threshold:
                    matched_model = "manual trigger" if manual_trigger else max(scores, key=scores.get)
                    print(f"[VoiceLoop] Wake detected! ({matched_model}, score={max_score:.2f})", flush=True)

                    manual_trigger = False
                    oww.reset()
                    buf = list(preroll)
                    speech_detected = False
                    consecutive_quiet = 0
                    state = "REC"
                    events.put({"type": "wake"})

            elif state == "REC":
                buf.append(pcm)
                energy = float(np.abs(pcm).mean())
                is_loud = energy > speech_threshold

                elapsed_sec = len(buf) * FRAME / SR

                # Don't let the tail of the wake word trigger speech_detected immediately.
                # Allow a brief 0.35s grace window before arming speech onset.
                if elapsed_sec > 0.35 and is_loud:
                    speech_detected = True
                    consecutive_quiet = 0
                else:
                    consecutive_quiet += 1

                quiet_sec = consecutive_quiet * FRAME / SR

                # Stop conditions:
                # 1. User was speaking and then paused for >= 1.4s
                # 2. User woke up the assistant but didn't speak within 4.5s
                # 3. Maximum recording time exceeded (15s)
                stop = False
                if speech_detected and quiet_sec >= 1.4:
                    stop = True
                elif (not speech_detected) and elapsed_sec >= 4.5:
                    print("[VoiceLoop] No speech detected within 4.5s grace period.", flush=True)
                    stop = True
                elif elapsed_sec >= MAX_SEC:
                    print("[VoiceLoop] Max recording duration reached.", flush=True)
                    stop = True

                if stop:
                    rec_duration = len(buf) * FRAME / SR
                    if speech_detected:
                        print(f"[VoiceLoop] Recording finished ({rec_duration:.1f}s). Transcribing...", flush=True)
                        audio = np.concatenate(buf).astype(np.float32) / 32768.0
                        try:
                            model = _get_model()
                            lang = getattr(settings, "whisper_language", "en")
                            segs, _ = model.transcribe(
                                audio,
                                language=lang,
                                beam_size=5,
                                vad_filter=True,
                                vad_parameters=dict(onset=0.35, min_silence_duration_ms=400),
                                initial_prompt="Open Chrome, open Gmail, open email, volume up, brightness down, write an email, search YouTube.",
                            )
                            text = " ".join(s.text.strip() for s in segs).strip()
                        except Exception as e:
                            print(f"[VoiceLoop] Transcription error: {e}", flush=True)
                            text = ""

                        if text:
                            print(f"[VoiceLoop] Transcribed: {text}", flush=True)
                            events.put({"type": "transcript", "text": text})
                        else:
                            print("[VoiceLoop] Transcription empty.", flush=True)
                            events.put({"type": "transcript", "text": ""})
                    else:
                        events.put({"type": "transcript", "text": ""})

                    state = "WAIT"
                    buf = []
                    preroll.clear()
                    oww.reset()

def run():
    while True:
        try:
            _run_loop()
        except KeyboardInterrupt:
            print("[VoiceLoop] Shutting down.", flush=True)
            break
        except Exception as e:
            print(f"[VoiceLoop] Error in voice loop: {e}. Retrying in 3 seconds...", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(3)

def start_loop():
    threading.Thread(target=run, daemon=True).start()
