#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 가상환경 활성화
source venv/bin/activate

echo "=========================================="
echo "  실시간 일-한 번역기 서버 시작"
echo "  http://localhost:8000"
echo "=========================================="
echo ""
echo "[주의] Ollama가 실행 중이어야 합니다:"
echo "  ollama serve"
echo "  ollama pull gemma3n:e2b"
echo ""

# Google Docs 인증 (GOOGLE_DOC_ID가 설정되고 token.json이 없을 때만 실행)
if [ -n "$GOOGLE_DOC_ID" ] && [ -f "credentials.json" ] && [ ! -f "token.json" ]; then
  echo "[Google Docs] 브라우저에서 인증을 완료해주세요..."
  python -c "from google_docs import _get_service; _get_service(); print('[Google Docs] 인증 완료!')"
fi

# 이미 캐시된 모델을 사용할 때 HuggingFace 네트워크 호출 차단 (401 오류 방지)
export HF_HUB_OFFLINE=1

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
