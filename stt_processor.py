"""
STT Processor: mlx-whisper 기반 실시간 음성인식 모듈 (Apple Silicon 최적화)

동작 방식:
- 브라우저에서 받은 Float32 PCM 청크를 내부 버퍼에 누적
- 에너지 기반 VAD로 발화 끝(묵음 구간) 감지 후 mlx_whisper 추론
- 버퍼가 MAX_BUFFER_SEC를 초과하면 강제 처리
- 발화 중간에도 3초마다 partial 결과 전송

v2 품질 개선 사항:
- condition_on_previous_text=False: 이전 세그먼트 오류의 연쇄 전파 차단
- logprob_threshold=-1.0: Whisper 기본값 복원 (과도한 필터링 완화)
- SILENCE_DURATION_SEC 1.0s: 일본어 문장 내 짧은 호흡 간격 오인식 방지
- fallback temperatures: 낮은 신뢰도 시 자동 재추론
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time

import numpy as np
import mlx_whisper

_JA_SENT_END = re.compile(r"(?<=[。！？…\n])\s*")

# 구두점 스타일 모방 + 기술/비즈니스 용어 명시로 고유명사 오인식 방지
_WHISPER_INITIAL_PROMPT = (
    "日本語の会話を句読点付きで正確に書き起こしてください。"
    "AI、ChatGPT、OpenAI、API、GPT-4、Claude、Gemini、Python、JavaScript、"
    "機械学習、ディープラーニング、プログラミング、アプリ、スマートフォン。"
    "例：ChatGPTを使って効率化しましょう。OpenAIのAPIにアクセスしてください。"
    "ありがとうございます。少々お待ちください。よろしくお願いします。"
)


def _split_sentences(text: str) -> list[str]:
    """일본어 문장 종결 부호 기준으로 분리. 부호 없으면 원문 그대로."""
    parts = [s.strip() for s in _JA_SENT_END.split(text) if s.strip()]
    return parts if parts else [text]


# Whisper가 묵음·저신뢰 구간에서 반복 생성하는 환각 패턴
_HALLUCINATION_RE = re.compile(
    r"ご視聴ありがとう|チャンネル登録|高評価|ご覧いただき|最後までご覧"
    r"|ありがとうございました|字幕.*作成|翻訳.*提供"
    r"|시청.*감사|구독.*좋아요|자막.*제공"
    r"|Thank you for watching|Please subscribe|Like and subscribe",
    re.IGNORECASE,
)


def _is_hallucination(text: str) -> bool:
    """알려진 Whisper 환각 패턴이면 True."""
    if _HALLUCINATION_RE.search(text):
        return True
    # 동일 문자열 반복 (예: "はははははは") — 압축비 기반 간이 판별
    if len(text) >= 8 and len(set(text)) / len(text) < 0.15:
        return True
    return False

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"

# VAD 파라미터
SILENCE_RMS_THRESHOLD = 0.008   # 이 값 미만 RMS = 묵음
SILENCE_DURATION_SEC  = 1.0     # 일본어 문장 내 짧은 호흡 간격 오인식 방지 (0.7 → 1.0)

# 처리 트리거
MIN_SPEECH_SEC  = 0.5   # 짧은 발화도 처리 가능하도록 완화 (1.0 → 0.5)
MAX_BUFFER_SEC  = 10.0  # 연속 발화 허용 시간 확대 (8.0 → 10.0)
PARTIAL_INTERVAL_SEC = 3.0  # partial 결과 전송 간격
PARTIAL_MIN_SEC = 2.0   # partial 추론 최소 버퍼 길이 — 미달 시 할루시네이션 빈발하여 생략

# Whisper 추론 파라미터 — 한 곳에서 관리
_WHISPER_PARAMS = dict(
    path_or_hf_repo=MODEL_REPO,
    language="ja",
    # 0.0 → 0.2 → 0.4 순으로 fallback 재시도 (낮은 신뢰도 자동 복구)
    temperature=(0.0, 0.2, 0.4),
    no_speech_threshold=0.6,
    # Whisper 기본값(-1.0) 복원 — 이전 -0.8은 실제 발화도 제거하던 문제 수정
    logprob_threshold=-1.0,
    compression_ratio_threshold=2.4,
    # 이전 세그먼트 텍스트를 다음 추론에 주입하지 않음 → 할루시네이션 연쇄 차단
    condition_on_previous_text=False,
    word_timestamps=False,
    verbose=False,
    initial_prompt=_WHISPER_INITIAL_PROMPT,
)


class MlxSTTSession:
    """
    WebSocket 연결 1개당 1개 생성되는 STT 세션.
    - push(audio_chunk): WebSocket 핸들러에서 호출
    - start() / stop(): 세션 생명주기 제어
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        out_queue: asyncio.Queue,
    ) -> None:
        self._loop = loop
        self._out_queue = out_queue

        self._buf: np.ndarray = np.empty(0, dtype=np.float32)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_partial_time = 0.0

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def push(self, audio: np.ndarray) -> None:
        with self._lock:
            self._buf = np.append(self._buf, audio)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("MlxSTTSession 스레드 시작")

    def stop(self) -> None:
        self._stop_event.set()

    # ── 내부 처리 루프 ────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                time.sleep(0.05)
                self._tick()
        except Exception:
            logger.exception("MlxSTTSession 스레드 예외")

    def _tick(self) -> None:
        with self._lock:
            buf = self._buf.copy()

        buf_sec = len(buf) / SAMPLE_RATE
        if buf_sec < MIN_SPEECH_SEC:
            return

        silence_samples = int(SILENCE_DURATION_SEC * SAMPLE_RATE)
        tail = buf[-silence_samples:] if len(buf) >= silence_samples else buf
        is_silent = self._rms(tail) < SILENCE_RMS_THRESHOLD

        # 버퍼 전체가 묵음이면 버퍼만 비우고 Whisper 호출 생략
        if is_silent and self._rms(buf) < SILENCE_RMS_THRESHOLD:
            with self._lock:
                self._buf = np.empty(0, dtype=np.float32)
            return

        force = buf_sec >= MAX_BUFFER_SEC

        if is_silent or force:
            self._transcribe(buf, final=True)
            with self._lock:
                self._buf = np.empty(0, dtype=np.float32)
            self._last_partial_time = time.time()
        elif time.time() - self._last_partial_time >= PARTIAL_INTERVAL_SEC:
            if buf_sec >= PARTIAL_MIN_SEC:
                self._transcribe(buf, final=False)
                self._last_partial_time = time.time()

    def _transcribe(self, audio: np.ndarray, *, final: bool) -> None:
        try:
            result = mlx_whisper.transcribe(audio, **_WHISPER_PARAMS)
            text = result.get("text", "").strip()
            if not text or _is_hallucination(text):
                if text:
                    logger.debug("환각 필터 제거: %s", text)
                return

            if final:
                segments = result.get("segments", [])
                raw_sentences = (
                    [seg.get("text", "").strip() for seg in segments]
                    if segments else [text]
                )
                for raw in raw_sentences:
                    if not raw or _is_hallucination(raw):
                        continue
                    for sentence in _split_sentences(raw):
                        logger.info("확정: %s", sentence)
                        self._send({"type": "stt", "text": sentence})
            else:
                logger.info("미리보기: %s", text)
                self._send({"type": "partial", "text": text})
        except Exception:
            logger.exception("mlx_whisper 추론 오류")

    # ── 유틸 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _rms(audio: np.ndarray) -> float:
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio ** 2)))

    def _send(self, payload: dict) -> None:
        self._loop.call_soon_threadsafe(self._out_queue.put_nowait, payload)
