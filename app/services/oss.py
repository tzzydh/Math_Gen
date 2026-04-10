import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from urllib.parse import urlparse
from uuid import uuid4

import oss2

from app.core.config import settings


class OssService:
    def __init__(self) -> None:
        if not settings.oss_access_key_id or not settings.oss_access_key_secret:
            raise ValueError("oss access keys not configured")
        if not settings.oss_endpoint or not settings.oss_bucket:
            raise ValueError("oss endpoint or bucket not configured")
        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        self.bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)

    def build_object_key(self, user_id: int, filename: str, directory: str = "questions") -> str:
        suffix = PurePosixPath(filename).suffix.lower()
        safe_directory = directory.strip("/").replace("..", "") or "questions"
        return f"uploads/{safe_directory}/{user_id}/{uuid4().hex}{suffix}"

    def sign_put_url(self, object_key: str, expires: int = 600) -> str:
        return self.bucket.sign_url("PUT", object_key, expires)

    def get_upload_host(self) -> str:
        if settings.oss_provider != "aliyun":
            raise ValueError(f"unsupported oss provider: {settings.oss_provider}")

        endpoint = settings.oss_endpoint.strip()
        parsed = urlparse(endpoint)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{settings.oss_bucket}.{parsed.netloc}"
        return f"https://{settings.oss_bucket}.{endpoint}"

    def generate_post_policy(
        self,
        object_key: str,
        content_type: str,
        expires_in: int | None = None,
        max_size: int = 20 * 1024 * 1024,
    ) -> dict[str, object]:
        if settings.oss_provider != "aliyun":
            raise ValueError(f"unsupported oss provider: {settings.oss_provider}")

        expire_seconds = expires_in or settings.oss_upload_expire_seconds
        expiration = (datetime.now(timezone.utc) + timedelta(seconds=expire_seconds)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        policy_dict = {
            "expiration": expiration,
            "conditions": [
                {"bucket": settings.oss_bucket},
                {"key": object_key},
                ["content-length-range", 1, max_size],
            ],
        }
        policy = base64.b64encode(
            json.dumps(policy_dict, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")
        signature = base64.b64encode(
            hmac.new(
                settings.oss_access_key_secret.encode("utf-8"),
                policy.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        return {
            "upload_host": self.get_upload_host(),
            "expires_in": expire_seconds,
            "form_data": {
                "key": object_key,
                "policy": policy,
                "OSSAccessKeyId": settings.oss_access_key_id,
                "Signature": signature,
                "success_action_status": "200",
            },
        }

    def public_url(self, object_key: str) -> str:
        base_url = settings.oss_public_base_url.rstrip("/") or self.get_upload_host()
        return f"{base_url}/{object_key}"

    def put_object(self, object_key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        headers = {"Content-Type": content_type}
        self.bucket.put_object(object_key, content, headers=headers)
