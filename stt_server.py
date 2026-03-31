"""
faster-whisper STT WebSocket server
Usage:
  pip install -r requirements.txt
  python stt_server.py

Optional env vars:
  WHISPER_MODEL  = tiny | base | small | medium | large-v3  (default: small)
  WHISPER_DEVICE = cpu | cuda                               (default: cpu)
  PORT           = 8000                                     (default: 8000)
"""

import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")
DEVICE     = os.environ.get("WHISPER_DEVICE", "cpu")
PORT       = int(os.environ.get("PORT", "8000"))

# ---------------------------------------------------------------------------
# Model (loaded once at startup)
# ---------------------------------------------------------------------------
print(f"Loading Whisper model '{MODEL_SIZE}' on {DEVICE} …")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8")
print("Model ready.")

executor = ThreadPoolExecutor(max_workers=2)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _transcribe(audio_path: str, lang: str) -> str:
    """Synchronous transcription — run in thread executor."""
    language = None if lang == "auto" else lang
    segments, _ = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 200,
            "speech_pad_ms": 100,
        },
    )
    return "".join(s.text for s in segments).strip()


@app.websocket("/ws")
async def transcribe_ws(websocket: WebSocket, lang: str = "ko"):
    await websocket.accept()
    print(f"[connected] lang={lang}")

    loop = asyncio.get_event_loop()

    try:
        while True:
            audio_bytes: bytes = await websocket.receive_bytes()

            # Skip near-empty chunks (silence / padding)
            if len(audio_bytes) < 1_000:
                continue

            # Write to temp file then transcribe off the event loop
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            try:
                text = await loop.run_in_executor(
                    executor, _transcribe, tmp_path, lang
                )
                if text:
                    await websocket.send_text(text)
                    print(f"[transcribed] {text!r}")
            except Exception as e:
                print(f"[error] transcription failed: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    except WebSocketDisconnect:
        print("[disconnected]")
    except Exception as e:
        print(f"[error] websocket: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
