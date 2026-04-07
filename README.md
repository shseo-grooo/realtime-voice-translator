# 실시간 일-한 번역기

mlx-whisper + Ollama 기반 실시간 일본어 → 한국어 번역 시스템 (Apple Silicon 최적화)

---

## 전체 구조

```
realtime-voice-translator/
├── main.py              # FastAPI 서버 + WebSocket 엔드포인트
├── stt_processor.py     # mlx-whisper 기반 MlxSTTSession
├── translator.py        # Ollama API 비동기 호출 (JA→KO)
├── google_docs.py       # Google Docs API 연동 (선택)
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
            └─ MlxSTTSession.push()
                 └─ 에너지 VAD → 묵음 감지 후 mlx_whisper.transcribe()
                      └─ 확정 문장 → translate(text)
                           └─ Ollama HTTP (gemma3n:e2b)
                                └─ WebSocket JSON → 브라우저 UI
                                     └─ (선택) Google Docs 기록
```

### 주요 컴포넌트

| 파일 | 클래스/함수 | 역할 |
|------|------------|------|
| `stt_processor.py` | `MlxSTTSession` | 오디오 버퍼 누적, 에너지 VAD, mlx_whisper 추론 |
| `translator.py` | `translate()` | Ollama에 비동기 번역 요청 |
| `google_docs.py` | `append_translation()` | Google Doc 끝에 번역 결과 기록 |
| `main.py` | `/ws/translate` | WebSocket 연결 관리, STT 세션 시작, 번역 결과 전송 |

### VAD 및 환각 방지 설정

`stt_processor.py` 상단 상수값으로 조정 가능

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `SILENCE_RMS_THRESHOLD` | `0.008` | 이 RMS 미만이면 묵음으로 판정 |
| `SILENCE_DURATION_SEC` | `0.7s` | 이 시간 이상 묵음이면 발화 종료로 판단 |
| `MIN_SPEECH_SEC` | `1.0s` | 최소 이 시간 이상 쌓여야 추론 실행 |
| `MAX_BUFFER_SEC` | `8.0s` | 이 시간 초과 시 강제 처리 |
| `no_speech_threshold` | `0.6` | Whisper 무음 판정 민감도 |
| `compression_ratio_threshold` | `2.2` | 반복 텍스트(환각) 제거 |
| `logprob_threshold` | `-0.8` | 저신뢰 세그먼트 제거 |

---

## 초기 세팅

### 사전 요구사항

- **macOS + Apple Silicon** (M1/M2/M3) — mlx-whisper 필수 조건
- **Python 3.11+**
- **[Ollama](https://ollama.com)** 설치
- **ffmpeg** 설치

```bash
brew install ffmpeg
```

### 1. 가상환경 생성 및 의존성 설치

```bash
cd realtime-voice-translator

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

> `mlx-whisper`는 Apple Silicon 전용입니다. Intel Mac이나 Linux에서는 동작하지 않습니다.

### 2. Whisper 모델 다운로드 (최초 1회)

서버 최초 실행 시 Hugging Face에서 `mlx-community/whisper-large-v3-turbo` 모델이 자동 다운로드됩니다 (~800MB).
미리 받으려면:

```bash
source venv/bin/activate
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"
```

### 3. Ollama 모델 준비

```bash
# Ollama 서비스 시작 (이미 실행 중이면 생략)
ollama serve

# 번역 모델 다운로드 (최초 1회)
ollama pull gemma3n:e2b
```

### 4. (선택) Google Docs 연동 설정

번역 결과를 Google Docs에 실시간으로 기록하려면 아래 절차를 따릅니다.

#### 4-1. Google Cloud 프로젝트 설정

1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. **API 및 서비스** → **라이브러리** → `Google Docs API` 검색 후 활성화
3. **사용자 인증 정보** → **OAuth 2.0 클라이언트 ID** 생성
   - 애플리케이션 유형: **데스크톱 앱**
4. JSON 파일 다운로드 후 `credentials.json`으로 이름 변경하여 프로젝트 루트에 배치

#### 4-2. 의존성 추가 설치

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

#### 4-3. 최초 인증 (token.json 생성)

```bash
GOOGLE_DOC_ID=<문서_ID> python -c "from google_docs import _get_service; _get_service(); print('인증 완료!')"
```

> 브라우저가 열리면 Google 계정으로 로그인하고 권한을 허용합니다.
> 성공하면 `token.json`이 생성되어 이후 재인증 없이 사용 가능합니다.

#### 4-4. 문서 ID 확인 방법

Google Docs URL에서 `/d/` 다음 부분이 문서 ID입니다.

```
https://docs.google.com/document/d/<문서_ID>/edit
```

---

## 실행 방법

### 방법 A — 스크립트 사용

```bash
# Google Docs 없이 실행
./run.sh

# Google Docs 연동하여 실행
GOOGLE_DOC_ID=<문서_ID> ./run.sh
```

### 방법 B — 직접 실행

```bash
source venv/bin/activate

# Google Docs 없이 실행
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Google Docs 연동하여 실행
GOOGLE_DOC_ID=<문서_ID> python -m uvicorn main:app --host 0.0.0.0 --port 8000
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
| STT 모델 변경 | `stt_processor.py` → `MODEL_REPO` |
| VAD 감도 조정 | `stt_processor.py` → `SILENCE_RMS_THRESHOLD`, `SILENCE_DURATION_SEC` |
| 번역 모델 변경 | `translator.py` → `MODEL` |
| Ollama 서버 주소 | `translator.py` → `OLLAMA_URL` |
| 오디오 청크 크기 | `frontend/index.html` → `CHUNK_MS` |
| partial 전송 간격 | `stt_processor.py` → `PARTIAL_INTERVAL_SEC` |
