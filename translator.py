"""
Translator: 로컬 Ollama API를 통해 일본어 → 한국어 번역
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3n:e2b"

SYSTEM_PROMPT = (
    "You are a Japanese-to-Korean translator. "
    "Translate the given Japanese text into natural spoken Korean. "
    "Output ONLY the Korean translation. "
    "Do NOT output Chinese, English, Japanese, or any explanation. "
    "Korean only. No other language."
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


async def translate(japanese_text: str) -> str:
    """
    일본어 텍스트를 Ollama를 통해 한국어로 번역합니다.

    Args:
        japanese_text: 번역할 일본어 텍스트

    Returns:
        번역된 한국어 텍스트 (실패 시 빈 문자열)
    """
    if not japanese_text.strip():
        return ""

    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": japanese_text.strip(),
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 256,
            "num_ctx": 2048,     # KV 캐시 최소화 (기본 262144 → 2048)
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "")
            # </think> 이후 내용 추출 (thinking 모델 대응)
            if "</think>" in raw:
                cleaned = raw.split("</think>", 1)[-1].strip()
            else:
                cleaned = _THINK_RE.sub("", raw).strip()
            return cleaned
    except httpx.ConnectError:
        logger.error("Ollama 서버에 연결할 수 없습니다. ollama serve 실행 여부를 확인하세요.")
        return ""
    except Exception as exc:
        logger.exception("번역 중 오류 발생: %s", exc)
        return ""
