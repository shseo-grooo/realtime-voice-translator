"""
main.py: FastAPI 서버 + WebSocket 엔드포인트
- 브라우저에서 16kHz PCM float32 오디오 스트림을 수신
- MlxSTTSession으로 일본어 STT 수행 (Apple Silicon mlx-whisper)
- 확정 문장을 Ollama에 전달하여 한국어 번역
- 결과를 JSON으로 클라이언트에 반환
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from stt_processor import SAMPLE_RATE, MlxSTTSession
from translator import translate
from google_docs import append_translation, is_configured

# 환경변수 GOOGLE_DOC_ID 또는 .env 파일로 설정 (없으면 Docs 기록 비활성화)
import os
GOOGLE_DOC_ID = os.environ.get("GOOGLE_DOC_ID", "")
DOCS_ENABLED = bool(GOOGLE_DOC_ID) and is_configured()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Realtime Voice Translator (JA→KO)")

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.websocket("/ws/translate")
async def ws_translate(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info("클라이언트 연결: %s", client)

    loop = asyncio.get_event_loop()
    out_queue: asyncio.Queue = asyncio.Queue()

    session = MlxSTTSession(loop, out_queue)
    session.start()

    async def send_results():
        """out_queue에서 STT/번역 결과를 읽어 WebSocket으로 전송.
        번역은 순차 처리 — 이전 번역이 끝난 뒤 다음 요청.
        """
        translate_queue: asyncio.Queue = asyncio.Queue()

        async def translation_worker():
            while True:
                item = await translate_queue.get()
                if item is None:
                    break
                stt_text, ws_ref = item
                translation = await translate(stt_text)
                if translation:
                    logger.info("번역 결과: %s", translation)
                    try:
                        await ws_ref.send_text(
                            json.dumps(
                                {"type": "translation", "text": translation},
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        pass
                    # Google Docs에 비동기 기록 (실패해도 번역 흐름 무관)
                    if DOCS_ENABLED:
                        asyncio.get_event_loop().run_in_executor(
                            None, append_translation, GOOGLE_DOC_ID, stt_text, translation
                        )

        worker_task = asyncio.create_task(translation_worker())

        try:
            while True:
                payload = await out_queue.get()
                if payload is None:
                    break

                msg_type = payload.get("type")
                text = payload.get("text", "")

                if msg_type == "partial":
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                    continue

                if msg_type == "stt":
                    logger.info("STT 확정: %s", text)
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                    await translate_queue.put((text, websocket))
        finally:
            await translate_queue.put(None)
            await worker_task

    sender_task = asyncio.create_task(send_results())

    try:
        async for message in websocket.iter_bytes():
            audio_chunk = np.frombuffer(message, dtype=np.float32)

            # 50ms 미만 청크 무시
            if len(audio_chunk) < int(SAMPLE_RATE * 0.05):
                continue

            session.push(audio_chunk)

    except WebSocketDisconnect:
        logger.info("클라이언트 연결 종료: %s", client)
    except Exception as exc:
        logger.exception("WebSocket 오류: %s", exc)
    finally:
        session.stop()
        await out_queue.put(None)
        sender_task.cancel()
        logger.info("클라이언트 정리 완료: %s", client)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
