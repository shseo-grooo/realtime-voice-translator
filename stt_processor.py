"""
STT Processor: whisper-streaming 기반 실시간 음성인식 모듈
- WebSocket으로 받은 오디오를 ASRProcessor에 밀어넣는 커스텀 AudioReceiver
- 확정된 텍스트를 asyncio 루프로 안전하게 전달하는 커스텀 OutputSender
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from dataclasses import dataclass

import numpy as np

from whisper_streaming import (
    ASRProcessor,
    AudioReceiver,
    Backend,
    OutputSender,
    TimeTrimming,
    Word,
)
from whisper_streaming.backend import (
    FasterWhisperFeatureExtractorConfig,
    FasterWhisperModelConfig,
    FasterWhisperTranscribeConfig,
)

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

# ── 1. AudioReceiver: WebSocket 오디오 청크를 ASRProcessor로 전달 ──────────────

class WebSocketAudioReceiver(AudioReceiver):
    """
    외부에서 push(numpy_array)를 호출하면 ASRProcessor 쪽으로 오디오를 전달합니다.
    stop()을 호출하면 _do_receive가 None을 반환하여 스레드가 종료됩니다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._input_queue: queue.Queue = queue.Queue()

    def push(self, audio: np.ndarray) -> None:
        """WebSocket 핸들러가 오디오 청크를 밀어넣을 때 사용."""
        self._input_queue.put_nowait(audio)

    def request_stop(self) -> None:
        """연결 종료 시 호출하여 receiver 스레드를 정지."""
        self._input_queue.put_nowait(None)

    # ── AudioReceiver 추상 메서드 구현 ──

    def _do_receive(self) -> np.ndarray | None:
        """
        오디오 청크가 도착할 때까지 최대 2초 대기.
        None 반환 시 AudioReceiver._run이 stopped를 set하고 종료.
        """
        try:
            data = self._input_queue.get(timeout=2.0)
            return data  # numpy array 또는 None(stop 신호)
        except queue.Empty:
            # 2초 이상 오디오가 없으면 연결이 끊겼다고 판단
            return None

    def _do_close(self) -> None:
        pass


# ── 2. OutputSender: 확정 텍스트를 asyncio Queue로 전달 ───────────────────────

class WebSocketOutputSender(OutputSender):
    """
    ASRProcessor가 Word를 확정하면 _do_output이 호출됩니다.
    asyncio 루프와의 스레드 경계를 call_soon_threadsafe로 안전하게 넘깁니다.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, out_queue: asyncio.Queue) -> None:
        super().__init__()
        self._loop = loop
        self._out_queue = out_queue
        # 일본어 문장 누적 버퍼
        self._text_buf: list[str] = []
        self._lock = threading.Lock()

    # ── OutputSender 추상 메서드 구현 ──

    def _do_output(self, word: Word) -> None:
        """
        확정된 Word를 받아 문장 단위로 묶어 asyncio Queue에 전달.
        일본어 마침표(。！？)를 기준으로 문장 완성 판단.
        """
        with self._lock:
            self._text_buf.append(word.word)
            accumulated = "".join(self._text_buf)

            # 문장 종결 문자가 포함되면 번역 대상으로 전송
            sentence_enders = {"。", "！", "？", ".", "!", "?", "\n"}
            last_cut = -1
            for i, ch in enumerate(accumulated):
                if ch in sentence_enders:
                    last_cut = i

            if last_cut >= 0:
                sentence = accumulated[: last_cut + 1].strip()
                remainder = accumulated[last_cut + 1 :]
                self._text_buf = [remainder] if remainder else []

                if sentence:
                    self._send({"type": "stt", "text": sentence})
            else:
                # 문장이 완성되지 않았어도 현재 누적 상태를 미리보기로 전송
                if accumulated.strip():
                    self._send({"type": "partial", "text": accumulated.strip()})

    def flush(self) -> None:
        """연결 종료 시 남은 버퍼를 강제 전송."""
        with self._lock:
            text = "".join(self._text_buf).strip()
            self._text_buf = []
            if text:
                self._send({"type": "stt", "text": text})

    def _send(self, payload: dict) -> None:
        self._loop.call_soon_threadsafe(self._out_queue.put_nowait, payload)

    def _do_close(self) -> None:
        self.flush()


# ── 3. ASRProcessor 생성 팩토리 ───────────────────────────────────────────────

def create_processor(
    audio_receiver: WebSocketAudioReceiver,
    output_sender: WebSocketOutputSender,
) -> ASRProcessor:
    """
    Faster-Whisper large-v3-turbo 기반 ASRProcessor를 생성합니다.

    VAD + hallucination 방지 설정:
    - vad_filter=True: 무음 구간을 잘라내어 환각 방지
    - repetition_penalty=1.3: 반복 텍스트 생성 억제
    - no_speech_threshold=0.6: 음성 없음 감지 민감도
    - hallucination_silence_threshold=2.0: 2초 이상 무음이면 결과 버림
    - temperature=[0.0]: 그리디 디코딩으로 속도 향상 및 안정성 확보
    """
    model_config = FasterWhisperModelConfig(
        model_size_or_path="large-v3-turbo",
        device="auto",
        compute_type="int8",
    )

    transcribe_config = FasterWhisperTranscribeConfig(
        task="transcribe",
        # VAD로 무음 구간 제거 → 환각 감소
        vad_filter=True,
        vad_parameters={
            "threshold": 0.45,
            "min_speech_duration_ms": 200,
            "min_silence_duration_ms": 600,
            "speech_pad_ms": 100,
        },
        # 반복/환각 억제
        repetition_penalty=1.3,
        no_speech_threshold=0.6,
        hallucination_silence_threshold=2.0,
        # 그리디 디코딩 (온도=0 고정)
        temperature=[0.0],
        beam_size=5,
        # 일본어 전용 설정
        suppress_blank=True,
    )

    feature_extractor_config = FasterWhisperFeatureExtractorConfig()

    processor_config = ASRProcessor.ProcessorConfig(
        sampling_rate=SAMPLE_RATE,
        prompt_size=200,
        # 오디오가 없을 때 5초 후 자동 종료
        audio_receiver_timeout=5.0,
        # SentenceTrimming은 미구현 → TimeTrimming 사용 (30초 컨텍스트 유지)
        audio_trimming=TimeTrimming(seconds=30.0),
        language="ja",
    )

    return ASRProcessor(
        processor_config=processor_config,
        audio_receiver=audio_receiver,
        output_senders=output_sender,
        backend=Backend.FASTER_WHISPER,
        model_config=model_config,
        transcribe_config=transcribe_config,
        feature_extractor_config=feature_extractor_config,
    )
