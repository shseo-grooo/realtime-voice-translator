# 실시간 일-한 번역기

whisper-streaming + Ollama 기반 실시간 일본어 → 한국어 번역 시스템

---

## 전체 구조

```
realtime-voice-translator2/
├── main.py              # FastAPI 서버 + WebSocket 엔드포인트
├── stt_processor.py     # whisper-streaming ASRProcessor 래퍼
├── translator.py        # Ollama API 비동기 호출 (JA→KO)
├── frontend/
│   └── index.html       # AudioWorklet 기반 마이크 UI
├── requirements.txt
├── run.sh
└── venv/                # Python 가상환경 (gitignore 대상)
```

### 데이터 흐름

```
브라우저 마이크
  └─ AudioWorklet (16kHz PCM Float32, 250ms 청크)
       └─ WebSocket binary → main.py
            └─ WebSocketAudioReceiver.push()
                 └─ ASRProcessor (별도 스레드, large-v3-turbo)
                      └─ 문장 확정 시 WebSocketOutputSender._do_output()
                           └─ asyncio Queue → translate(text)
                                └─ Ollama HTTP (gemma4:e4b)
                                     └─ WebSocket JSON → 브라우저 UI
```

### 주요 컴포넌트

| 파일 | 클래스/함수 | 역할 |
|------|------------|------|
| `stt_processor.py` | `WebSocketAudioReceiver` | WebSocket 오디오 청크를 ASRProcessor 큐에 전달 |
| `stt_processor.py` | `WebSocketOutputSender` | 확정된 Word를 asyncio 루프로 안전하게 전달, 일본어 문장 단위 버퍼링 |
| `stt_processor.py` | `create_processor()` | VAD·환각 방지 설정이 적용된 ASRProcessor 생성 |
| `translator.py` | `translate()` | Ollama에 비동기 번역 요청 |
| `main.py` | `/ws/translate` | WebSocket 연결 관리, STT 스레드 시작, 번역 결과 전송 |

### 환각/무한루프 방지 설정

`stt_processor.py` → `FasterWhisperTranscribeConfig`

| 옵션 | 값 | 효과 |
|------|----|------|
| `vad_filter` | `True` | 무음 구간 제거 |
| `vad_parameters.threshold` | `0.45` | VAD 감도 |
| `repetition_penalty` | `1.3` | 반복 텍스트 억제 |
| `hallucination_silence_threshold` | `2.0` | 2초 이상 무음이면 결과 버림 |
| `temperature` | `[0.0]` | 그리디 디코딩 (안정적 출력) |
| `no_speech_threshold` | `0.6` | 무음 감지 민감도 |

---

## 초기 세팅

### 사전 요구사항

- Python 3.11+
- [Ollama](https://ollama.com) 설치

### 1. 가상환경 생성 및 의존성 설치

```bash
cd realtime-voice-translator2

python3 -m venv venv
source venv/bin/activate

# 핵심 패키지
pip install fastapi uvicorn websockets httpx numpy

# STT 엔진
pip install faster-whisper
pip install whisper-streaming --no-deps   # pyalsaaudio는 Linux 전용이므로 --no-deps
pip install mosestokenizer                 # whisper-streaming 런타임 의존성
```

> `pyalsaaudio`는 Linux 전용 오디오 라이브러리입니다. macOS에서는 `--no-deps` 플래그로 건너뜁니다.

### 2. Ollama 모델 준비

```bash
# Ollama 서비스 시작 (이미 실행 중이면 생략)
ollama serve

# 번역에 사용할 모델 다운로드 (최초 1회)
ollama pull gemma4:e4b
```

### 3. Whisper 모델 다운로드 확인

`large-v3-turbo` 모델은 서버 최초 실행 시 Hugging Face에서 자동 다운로드됩니다 (~800MB). 미리 받으려면:

```bash
source venv/bin/activate
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='auto', compute_type='int8')"
```

---

## 실행 방법

### 방법 A — 스크립트 사용

```bash
./run.sh
```

### 방법 B — 직접 실행

```bash
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 브라우저 접속

```
http://localhost:8000
```

1. **마이크 시작** 버튼 클릭 → 브라우저 마이크 권한 허용
2. 일본어로 말하면 화면 상단에 인식 중 텍스트(미리보기) 표시
3. 문장이 완성되면 하단에 일본어 원문 + 한국어 번역 표시

---

## WebSocket 메시지 형식

서버 → 클라이언트 (JSON)

| `type` | 설명 | 예시 |
|--------|------|------|
| `partial` | STT 미리보기 (미확정) | `{"type":"partial","text":"こんにち"}` |
| `stt` | 확정된 일본어 문장 | `{"type":"stt","text":"こんにちは。"}` |
| `translation` | 번역된 한국어 | `{"type":"translation","text":"안녕하세요."}` |

---

## 설정 변경

| 변경 항목 | 위치 |
|-----------|------|
| STT 모델 변경 | `stt_processor.py` → `FasterWhisperModelConfig.model_size_or_path` |
| VAD 감도 조정 | `stt_processor.py` → `vad_parameters` |
| 번역 모델 변경 | `translator.py` → `MODEL` |
| Ollama 서버 주소 | `translator.py` → `OLLAMA_URL` |
| 오디오 청크 크기 | `frontend/index.html` → `CHUNK_MS` |
| 컨텍스트 유지 시간 | `stt_processor.py` → `TimeTrimming(seconds=30.0)` |
