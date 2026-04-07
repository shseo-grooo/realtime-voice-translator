"""
google_docs.py: Google Docs API 연동 — 번역 결과 실시간 기록
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/documents"]
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

_service = None  # 서비스 싱글톤


def _get_service():
    global _service
    if _service is not None:
        return _service

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                raise FileNotFoundError(
                    "credentials.json 파일이 없습니다. "
                    "Google Cloud Console에서 다운로드 후 프로젝트 루트에 놓아주세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    _service = build("docs", "v1", credentials=creds)
    logger.info("Google Docs API 연결 완료")
    return _service


def append_translation(doc_id: str, japanese: str, korean: str) -> None:
    """
    Google Doc 끝에 번역 결과 한 줄을 추가합니다.

    형식:  [HH:MM:SS] 日本語原文 → 한국어 번역
    """
    try:
        service = _get_service()
        doc = service.documents().get(documentId=doc_id).execute()

        # 문서 마지막 위치
        end_index = doc["body"]["content"][-1]["endIndex"] - 1

        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {japanese} → {korean}\n\n"

        service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": end_index},
                            "text": line,
                        }
                    }
                ]
            },
        ).execute()

        logger.info("Google Docs 기록: %s", line.strip())

    except Exception:
        logger.exception("Google Docs 기록 실패")


def is_configured() -> bool:
    """credentials.json 또는 token.json이 존재하면 True."""
    return os.path.exists(CREDS_FILE) or os.path.exists(TOKEN_FILE)
