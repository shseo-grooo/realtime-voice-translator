# 프로젝트 사양서: whisper-streaming 기반 실시간 일-한 번역기

## 1. 프로젝트 개요
`whisper-streaming` 오픈소스를 엔진으로 사용하여, 일본어 음성 입력을 실시간으로 인식하고 로컬 LLM을 통해 한국어로 즉각 번역하는 시스템을 구축한다.

## 2. 핵심 기술 스택
* **STT Engine:** `whisper-streaming` (Faster-Whisper 기반 라이브러리)
* **Model:** `large-v3-turbo` (속도와 정확도의 최적 접점)
* **Language:** Input `Japanese (ja)`, Translation Target `Korean (ko)`
* **LLM:** `Ollama` (gemma3n:e2b)
* **Communication:** WebSockets (Binary Audio Stream)

## 3. 핵심 아키텍처 및 로직

### A. Whisper-Streaming 동작 원리
1.  **Continuous Buffer:** 오디오를 고정된 크기로 자르는 것이 아니라, 스트리밍 버퍼에 계속 쌓으면서 문맥을 유지합니다.
2.  **Look-ahead Window:** 모델이 아직 확정되지 않은 문장의 끝부분을 예측하며 실시간으로 텍스트를 업데이트합니다.

### B. LLM 번역 전략 (Stability Check)
* STT 결과가 "확정(Finalized)" 상태이거나, 특정 시간 동안 텍스트 변화가 없을 때만 LLM에 번역을 요청하여 API 호출 낭비를 방지합니다.
* **System Prompt:** "너는 실시간 대화 통역사야. 일본어 입력을 문맥에 맞는 자연스러운 한국어 구어체로 짧고 빠르게 번역해."

## 4. Claude Code를 위한 파일 구성 가이드

### 주요 파일 리스트
1.  **`main.py`**: FastAPI 서버 및 WebSocket 엔드포인트 관리.
2.  **`stt_processor.py`**: `WhisperStreaming` 클래스를 인스턴스화하고 오디오 덩어리를 밀어넣는 핵심 로직.
3.  **`translator.py`**: Ollama API와 통신하여 번역 수행.
4.  **`frontend/app.js`**: `MediaRecorder` 또는 `AudioWorklet`을 사용해 16kHz 오디오 전송.

### 구현 시 주의사항 (Claude에게 강조할 점)
* **Latency 설정:** `min_chunk_size`를 0.5초~1초 사이로 조절하여 반응 속도를 최적화할 것.
* **GPU 메모리 관리:** Faster-Whisper 엔진과 LLM 모델이 VRAM을 공유하므로, `compute_type="int8"` 또는 `float16` 설정을 적절히 사용할 것.
* **일본어 특이사항:** 일본어 마침표(`。`)를 기준으로 문장을 분리하여 번역기로 넘길 것.
