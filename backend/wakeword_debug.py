"""
Diagnostic and test tool for wake-word detection using OpenWakeWord.
Run this script to verify your microphone and see real-time detection scores:
    python wakeword_debug.py
"""
import urllib.request
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

BACKEND_URL = "http://127.0.0.1:8765"
MODELS = ["hey_jarvis", "alexa"]
THRESHOLD = 0.5
SR = 16000
FRAME = 1280

print("[DEBUG] Listing audio input devices...", flush=True)
devices = sd.query_devices()
default_in = sd.default.device[0]
for idx, dev in enumerate(devices):
    if dev.get("max_input_channels", 0) > 0:
        marker = " -> [DEFAULT]" if idx == default_in else ""
        print(f"  [{idx}] {dev['name']}{marker}", flush=True)

print(f"\n[DEBUG] Loading OpenWakeWord models: {MODELS}...", flush=True)
oww = Model(wakeword_models=MODELS)

print("[DEBUG] Opening microphone stream...", flush=True)
with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=FRAME) as stream:
    print(f"\n[DEBUG] READY! Say 'Hey Jarvis' or 'Alexa' to test detection.")
    print("[DEBUG] Press Ctrl+C to stop.\n", flush=True)

    try:
        while True:
            frame, _ = stream.read(FRAME)
            pcm = frame[:, 0]
            scores = oww.predict(pcm)

            max_model = max(scores, key=scores.get)
            max_score = scores[max_model]
            energy = int(np.abs(pcm).mean())

            # Print a progress indicator when there is voice activity or high score
            if max_score > 0.1 or energy > 100:
                bar = "#" * int(max_score * 20)
                print(f"[DEBUG] Energy: {energy:4d} | Best: {max_model:10s} = {max_score:.2f} [{bar:<20s}]", flush=True)

            if max_score > THRESHOLD:
                print(f"\n[DEBUG] *** WAKE WORD DETECTED: '{max_model}' (score={max_score:.2f}) ***", flush=True)
                oww.reset()

                # Test sending trigger to backend
                try:
                    req = urllib.request.Request(
                        f"{BACKEND_URL}/voice/trigger",
                        data=b"{}",
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    resp = urllib.request.urlopen(req, timeout=1)
                    print(f"[DEBUG] Backend /voice/trigger response: {resp.status} OK\n", flush=True)
                except Exception as e:
                    print(f"[DEBUG] Backend trigger note: {e} (Backend might not be running)\n", flush=True)

    except KeyboardInterrupt:
        print("\n[DEBUG] Test stopped by user.", flush=True)
