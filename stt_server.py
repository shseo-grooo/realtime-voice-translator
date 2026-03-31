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

    # VAD disabled: let whisper handle all audio without pre-filtering.
    # Short clips (5s) with VAD enabled would often be filtered out entirely.
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    text = "".join(s.text for s in segments).strip()
    print(f"  detected language: {info.language} ({info.language_probability:.0%}), text: {text!r}")
    return text


@app.websocket("/ws")
async def transcribe_ws(websocket: WebSocket, lang: str = "ko"):
    await websocket.accept()
    print(f"[connected] lang={lang}")

    loop = asyncio.get_event_loop()

    try:
        while True:
            audio_bytes: bytes = await websocket.receive_bytes()
            print(f"[received] {len(audio_bytes):,} bytes")

            # Skip header-only blobs
            if len(audio_bytes) < 500:
                print(f"  skipped (too small)")
                continue

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            try:
                text = await loop.run_in_executor(
                    executor, _transcribe, tmp_path, lang
                )
                if text:
                    await websocket.send_text(text)
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
