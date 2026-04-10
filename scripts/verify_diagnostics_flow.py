#!/usr/bin/env python3
"""End-to-end verifier for the upload -> diagnostics flow."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import SessionLocal


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_QUESTION = (
    "\u5df2\u77e5\u7b49\u5dee\u6570\u5217{a_n}\u7684\u524dn\u9879\u548c\u4e3aS_n\uff0c"
    "\u82e5a_3+a_4=7\uff0c\u6c42S_10\u3002"
)
TEST_OPENID = "script_verify_openid"
TEST_UNIONID = "script_verify_unionid"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the diagnostics flow end-to-end.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL, default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="Question text to upload and classify.",
    )
    return parser.parse_args()


def ensure_test_user() -> User:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.openid == TEST_OPENID))
        if user is None:
            user = User(
                openid=TEST_OPENID,
                unionid=TEST_UNIONID,
                nickname="DiagVerifier",
                avatar_url="https://example.com/avatar.png",
                status="active",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def wait_for_api(base_url: str, timeout_seconds: int = 30) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/api/v1/health", timeout=2)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"API did not become healthy in time: {last_error}") from last_error


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    question_text = args.question.strip()
    if not question_text:
        raise SystemExit("Question text cannot be empty.")

    user = ensure_test_user()
    token = create_access_token(str(user.id), {"uid": user.id, "openid": user.openid})
    headers = {"Authorization": f"Bearer {token}"}

    health = wait_for_api(base_url)

    presign_response = requests.post(
        f"{base_url}/api/v1/uploads/presign",
        headers=headers,
        json={
            "filename": "verify-question.txt",
            "content_type": "text/plain",
            "directory": "diagnostic-tests",
        },
        timeout=15,
    )
    presign_response.raise_for_status()
    presign_data = presign_response.json()

    upload_response = requests.post(
        presign_data["upload_host"],
        data=presign_data["form_data"],
        files={"file": ("verify-question.txt", question_text.encode("utf-8"), "text/plain")},
        timeout=30,
    )
    upload_response.raise_for_status()

    confirm_response = requests.post(
        f"{base_url}/api/v1/uploads/confirm",
        headers=headers,
        json={
            "asset_id": presign_data["asset_id"],
            "size": len(question_text.encode("utf-8")),
            "mime_type": "text/plain",
            "sha256": "verify-diagnostics-flow",
        },
        timeout=15,
    )
    confirm_response.raise_for_status()
    confirm_data = confirm_response.json()

    diagnostic_response = requests.post(
        f"{base_url}/api/v1/diagnostics",
        headers=headers,
        json={"asset_id": presign_data["asset_id"]},
        timeout=30,
    )
    diagnostic_response.raise_for_status()
    diagnostic_data = diagnostic_response.json()

    lookup_response = requests.get(
        f"{base_url}/api/v1/diagnostics/{diagnostic_data['id']}",
        headers=headers,
        timeout=15,
    )
    lookup_response.raise_for_status()
    lookup_data = lookup_response.json()

    public_fetch = requests.get(confirm_data["public_url"], timeout=30)
    public_fetch.raise_for_status()

    summary = {
        "health": health,
        "asset_id": confirm_data["asset_id"],
        "diagnostic_id": diagnostic_data["id"],
        "diagnostic_status": diagnostic_data["status"],
        "chapter": diagnostic_data["result"]["chapter"],
        "confidence": diagnostic_data["result"]["confidence"],
        "knowledge_weights": diagnostic_data["result"]["knowledge_weights"],
        "source": diagnostic_data["result"]["source"],
        "oss_public_url": confirm_data["public_url"],
        "oss_fetch_status": public_fetch.status_code,
        "lookup_matches_create": lookup_data["id"] == diagnostic_data["id"],
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
