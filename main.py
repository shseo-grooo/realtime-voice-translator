"""
main.py: FastAPI 서버 + WebSocket 엔드포인트
- 브라우저에서 16kHz PCM float32 오디오 스트림을 수신
- ASRProcessor로 일본어 STT 수행
- 확정 문장을 Ollama에 전달하여 한국어 번역
- 결과를 JSON으로 클라이언트에 반환
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from stt_processor import (
    SAMPLE_RATE,
    WebSocketAudioReceiver,
    WebSocketOutputSender,
    create_processor,
)
from translator import translate

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

    audio_receiver = WebSocketAudioReceiver()
    output_sender = WebSocketOutputSender(loop, out_queue)
    processor = create_processor(audio_receiver, output_sender)

    # ASRProcessor를 별도 스레드에서 실행 (blocking)
    processor_thread = threading.Thread(target=processor.run, daemon=True)
    processor_thread.start()
    logger.info("ASRProcessor 스레드 시작")

    async def send_results():
        """out_queue에서 STT/번역 결과를 읽어 WebSocket으로 전송."""
        while True:
            payload = await out_queue.get()
            if payload is None:
                break

            msg_type = payload.get("type")
            text = payload.get("text", "")

            # partial: 미리보기용 STT 결과 (번역 없이 바로 전송)
            if msg_type == "partial":
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                continue

            # stt: 확정 문장 → 번역 요청
            if msg_type == "stt":
                logger.info("STT 확정: %s", text)
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))

                translation = await translate(text)
                if translation:
                    logger.info("번역 결과: %s", translation)
                    await websocket.send_text(
                        json.dumps(
                            {"type": "translation", "text": translation},
                            ensure_ascii=False,
                        )
                    )

    sender_task = asyncio.create_task(send_results())

    try:
        async for message in websocket.iter_bytes():
            # 브라우저에서 Float32LE PCM 데이터를 그대로 전송
            audio_chunk = np.frombuffer(message, dtype=np.float32)

            # 묵음/너무 짧은 청크 무시 (환각 방지)
            if len(audio_chunk) < int(SAMPLE_RATE * 0.05):  # 50ms 미만
                continue

            audio_receiver.push(audio_chunk)

    except WebSocketDisconnect:
        logger.info("클라이언트 연결 종료: %s", client)
    except Exception as exc:
        logger.exception("WebSocket 오류: %s", exc)
    finally:
        # 정리
        audio_receiver.request_stop()
        await out_queue.put(None)  # send_results 루프 종료
        sender_task.cancel()
        logger.info("클라이언트 정리 완료: %s", client)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
