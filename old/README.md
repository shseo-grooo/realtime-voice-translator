# 실시간 음성 번역

음성 입력을 실시간으로 번역해 텍스트로 보여주는 로컬 전용 웹앱.

- **STT**: faster-whisper (로컬 Python 서버)
- **번역**: Ollama gemma3n:e2b (로컬 LLM)
- **프레임워크**: Next.js (App Router, TypeScript, Tailwind CSS)

---

## 사전 요구사항

- Node.js 18+
- Python 3.9+
- [Ollama](https://ollama.com) 설치 및 실행

---

## 설치

### 1. Ollama 모델 다운로드

```bash
ollama pull gemma3n:e2b
```

### 2. Next.js 의존성 설치

```bash
npm install
```

### 3. Python 의존성 설치

```bash
pip install -r requirements.txt
```

> GPU 사용 시 faster-whisper의 CUDA 버전 설치를 권장합니다.
> ```bash
> pip install faster-whisper
> # CUDA가 있다면: WHISPER_DEVICE=cuda python stt_server.py
> ```

---

## 실행

서버 두 개를 각각 다른 터미널에서 실행합니다.

### 터미널 1 — STT 서버 (faster-whisper)

```bash
python stt_server.py
```

기본값: `small` 모델, CPU, 포트 `8000`

환경 변수로 설정 변경 가능:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `WHISPER_MODEL` | `small` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` / `cuda` |
| `PORT` | `8000` | 서버 포트 |

```bash
# 예시: 더 빠른 모델로 실행
WHISPER_MODEL=base python stt_server.py

# 예시: GPU + 고정밀 모델
WHISPER_MODEL=medium WHISPER_DEVICE=cuda python stt_server.py
```

### 터미널 2 — Next.js 개발 서버

```bash
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 접속.

---

## 환경 변수 (.env.local)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3n:e2b
NEXT_PUBLIC_STT_WS_URL=ws://localhost:8000/ws
```

---

## 아키텍처

```
브라우저
  ├─ MediaRecorder (2초 클립) ──WebSocket──► stt_server.py (faster-whisper)
  │                                              └─ 텍스트 반환
  └─ fetch /api/translate ──────────────────► Ollama gemma3n:e2b
                                                 └─ 번역 스트리밍 반환
```

---

## 주의사항

- Chrome 또는 Edge 브라우저 필요 (MediaRecorder WebM 지원)
- 마이크 사용 권한 허용 필요
- STT 서버(`localhost:8000`)와 Ollama(`localhost:11434`)가 모두 실행 중이어야 함
