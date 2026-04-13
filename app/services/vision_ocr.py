import base64
import json
import re
from functools import lru_cache
from typing import Any

from openai import OpenAI

from app.core.config import settings
from core.openai_compat import call_openai_vision_json

MATH_OCR_PROMPT = """
你是一位中国高中数学 OCR 助手。请识别图片中的数学题，并且只输出 JSON。
格式：
{"questions":[{"stem":"题干","options":["A","B","C","D"],"answer":"答案","analysis":"解析"}]}
要求：
1. 只输出 JSON。
2. 填空题、解答题如果没有选项，options 返回 []。
3. 没有可识别的数学题时返回 {"questions": []}。
""".strip()

CHINESE_ESSAY_OCR_PROMPT = """
你是一位高中语文作文 OCR 助手。请识别图片中的中文作文，并且只输出 JSON。
格式：
{"title":"作文标题","text":"作文全文","paragraphs":["第一段","第二段"]}
要求：
1. 忠实转写原文，保留错别字、病句和段落。
2. 没有标题时 title 返回空字符串。
3. 没有可识别作文时返回 {"title":"","text":"","paragraphs":[]}。
""".strip()

ENGLISH_ESSAY_OCR_PROMPT = """
You are an OCR assistant for high-school English essays. Read the essay image and return JSON only.
Format:
{"title":"essay title","text":"full essay text","paragraphs":["paragraph 1","paragraph 2"]}
Requirements:
1. Preserve the original wording, punctuation, spelling mistakes, and paragraph breaks.
2. If there is no title, return an empty string.
3. If there is no readable essay, return {"title":"","text":"","paragraphs":[]} only.
""".strip()


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


class VisionOcrService:
    def ensure_configured(self) -> None:
        api_key = settings.openai_api_key.strip()
        if not api_key or api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY is not configured for OCR")

    def extract_from_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> dict[str, Any]:
        payload = self._extract_json_from_image_bytes(image_bytes, mime_type, MATH_OCR_PROMPT)
        questions = payload.get("questions", [])
        return {
            "questions": questions,
            "text": self._questions_to_text(questions),
            "raw_output": payload.get("raw_output", ""),
        }

    def extract_chinese_essay_from_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> dict[str, Any]:
        return self._extract_essay_payload(image_bytes, mime_type, CHINESE_ESSAY_OCR_PROMPT)

    def extract_english_essay_from_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> dict[str, Any]:
        return self._extract_essay_payload(image_bytes, mime_type, ENGLISH_ESSAY_OCR_PROMPT)

    def _extract_essay_payload(self, image_bytes: bytes, mime_type: str, prompt: str) -> dict[str, Any]:
        payload = self._extract_json_from_image_bytes(image_bytes, mime_type, prompt)
        paragraphs_raw = payload.get("paragraphs")
        if isinstance(paragraphs_raw, list):
            paragraphs = [str(item).strip() for item in paragraphs_raw if str(item).strip()]
        else:
            paragraphs = []
        text = str(payload.get("text", "") or "").strip()
        if not text and paragraphs:
            text = "\n".join(paragraphs)
        return {
            "title": str(payload.get("title", "") or "").strip(),
            "text": text,
            "paragraphs": paragraphs,
            "raw_output": payload.get("raw_output", ""),
        }

    def _extract_json_from_image_bytes(self, image_bytes: bytes, mime_type: str, prompt: str) -> dict[str, Any]:
        self.ensure_configured()
        image_data_url = self._build_data_url(image_bytes=image_bytes, mime_type=mime_type)
        timeout = max(settings.ocr_timeout_seconds, 90)
        attempts = max(settings.ocr_retry_count, 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                raw_output = call_openai_vision_json(
                    client=get_openai_client(),
                    model=settings.openai_model_name,
                    prompt=prompt,
                    image_data_url=image_data_url,
                    timeout=timeout,
                )
                break
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "timed out" not in message and "timeout" not in message:
                    raise
        else:
            raise RuntimeError("OCR 识别超时，请稍后重试或手动补充作文原文。") from last_error

        payload = self._parse_json_payload(raw_output)
        payload["raw_output"] = raw_output
        return payload

    def _build_data_url(self, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _parse_json_payload(self, raw_text: str) -> dict[str, Any]:
        sanitized = raw_text.strip()
        sanitized = re.sub(r"^```json\s*", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"^```\s*", "", sanitized)
        sanitized = re.sub(r"\s*```$", "", sanitized)
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", sanitized, flags=re.DOTALL)
            if not match:
                raise ValueError("OCR response was not valid JSON")
            return json.loads(match.group(0))

    def _questions_to_text(self, questions: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for question in questions:
            stem = question.get("stem")
            if isinstance(stem, str) and stem.strip():
                parts.append(stem.strip())
            options = question.get("options")
            if isinstance(options, list):
                parts.extend(str(option).strip() for option in options if str(option).strip())
            analysis = question.get("analysis")
            if isinstance(analysis, str) and analysis.strip():
                parts.append(analysis.strip())
        return "\n".join(parts).strip()
