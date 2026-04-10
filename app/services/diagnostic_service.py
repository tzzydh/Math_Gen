import json
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from app.db.models.asset import Asset
from app.services.oss import OssService
from app.services.vision_ocr import VisionOcrService
from auto_classify import MathClassifier

ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_TREE_PATH = ROOT_DIR / "knowledge_tree.json"
TEXT_EXTENSIONS = {".txt", ".md"}
JSON_EXTENSIONS = {".json"}


@lru_cache(maxsize=1)
def get_classifier() -> MathClassifier:
    return MathClassifier(str(KNOWLEDGE_TREE_PATH))


class DiagnosticService:
    def __init__(self) -> None:
        self.classifier = get_classifier()
        self.oss_service = OssService()
        self.vision_ocr = VisionOcrService()

    def classify_asset(self, asset: Asset, raw_text: str | None = None) -> dict[str, Any]:
        source, payload, ocr_questions = self._resolve_payload(asset=asset, raw_text=raw_text)
        if isinstance(payload, dict):
            result = self.classifier.classify_question(payload)
            extracted_text = self._preview_from_question(payload)
        else:
            result = self.classifier.classify(payload)
            extracted_text = payload

        return {
            "source": source,
            "classification": result,
            "extracted_text_preview": extracted_text[:500],
            "asset_url": self.oss_service.public_url(asset.object_key),
            "ocr_questions": ocr_questions,
        }

    def _resolve_payload(
        self,
        asset: Asset,
        raw_text: str | None,
    ) -> tuple[str, str | dict[str, Any], list[dict[str, Any]]]:
        if raw_text and raw_text.strip():
            return "raw_text", raw_text.strip(), []

        suffix = PurePosixPath(asset.object_key).suffix.lower()
        mime_type = (asset.mime_type or "").lower()

        if mime_type.startswith("image/"):
            ocr_payload = self.vision_ocr.extract_from_image_bytes(
                image_bytes=self._download_asset_bytes(asset),
                mime_type=mime_type or self._infer_mime_type_from_suffix(suffix),
            )
            extracted_text = ocr_payload["text"].strip()
            if not extracted_text:
                raise ValueError("OCR completed but no readable math text was extracted from the image")
            questions = ocr_payload.get("questions", [])
            if len(questions) == 1 and isinstance(questions[0], dict):
                return "vision_ocr", questions[0], questions
            return "vision_ocr", extracted_text, questions

        content = self._download_asset_text(asset)
        if suffix in JSON_EXTENSIONS or "json" in mime_type:
            return "asset_json", self._parse_json_payload(content), []
        if suffix in TEXT_EXTENSIONS or mime_type.startswith("text/"):
            return "asset_text", content.strip(), []

        # Fall back to plain text for unknown text-like assets.
        return "asset_text", content.strip(), []

    def _download_asset_text(self, asset: Asset) -> str:
        url = self.oss_service.public_url(asset.object_key)
        with httpx.Client(timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _download_asset_bytes(self, asset: Asset) -> bytes:
        url = self.oss_service.public_url(asset.object_key)
        with httpx.Client(timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def _parse_json_payload(self, raw_text: str) -> dict[str, Any] | str:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload:
            first_item = payload[0]
            if isinstance(first_item, dict):
                return first_item
        raise ValueError("json asset must contain a question object or a non-empty question list")

    def _preview_from_question(self, question: dict[str, Any]) -> str:
        parts: list[str] = []
        stem = question.get("stem")
        if isinstance(stem, str):
            parts.append(stem)

        options = question.get("options")
        if isinstance(options, list):
            parts.extend(str(item) for item in options)

        analysis = question.get("analysis")
        if isinstance(analysis, str):
            parts.append(analysis)
        return " ".join(parts).strip()

    def _infer_mime_type_from_suffix(self, suffix: str) -> str:
        if suffix == ".jpg" or suffix == ".jpeg":
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
