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
echo "  ollama pull gemma4:e4b"
echo ""

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
