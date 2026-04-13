import json
import os
import re
import tempfile
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import Any
from xml.sax.saxutils import escape

import httpx
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.config import settings
from app.db.models.asset import Asset
from app.services.oss import OssService
from app.services.vision_ocr import VisionOcrService, get_openai_client
from core.openai_compat import call_openai_text_json

CHINESE_REVIEW_PROMPT = """
你是一位经验丰富的中国高中语文作文阅卷老师和润色编辑。请根据给定作文输出严格 JSON。
格式：
{{
  "corrected_title":"修改后的标题",
  "corrected_text":"润色后的全文",
  "summary":"整体点评",
  "score":48,
  "score_max":60,
  "strengths":["优点1","优点2"],
  "issues":["问题1","问题2"],
  "suggestions":["建议1","建议2"]
}}
要求：
1. 只输出 JSON。
2. corrected_text 必须是完整润色稿，保留原文主旨和文体。
3. score 使用 0-60 的整数。
4. strengths/issues/suggestions 各返回 2-5 条中文短句。
5. 如原文没有标题，可拟一个自然标题。

原作文标题：
{title}

原作文全文：
{text}
""".strip()

ENGLISH_REVIEW_PROMPT = """
You are a senior high-school English writing teacher. Review the essay and return strict JSON only.
Format:
{{
  "corrected_title":"revised title",
  "corrected_title_cn":"中文标题",
  "corrected_text":"full revised essay",
  "corrected_text_cn":"润色后全文的中文对照译文",
  "summary":"overall feedback",
  "summary_cn":"中文整体点评",
  "score":21,
  "score_max":25,
  "strengths":["strength 1","strength 2"],
  "strengths_cn":["优点1","优点2"],
  "issues":["issue 1","issue 2"],
  "issues_cn":["问题1","问题2"],
  "suggestions":["suggestion 1","suggestion 2"],
  "suggestions_cn":["建议1","建议2"]
}}
Requirements:
1. Return JSON only.
2. corrected_text must be a full polished version in natural English.
3. corrected_text_cn must be a fluent Chinese translation of corrected_text.
4. summary_cn / strengths_cn / issues_cn / suggestions_cn must be clear Chinese explanations for high-school students.
5. Keep the original topic and the student's intended meaning whenever possible.
6. score should be an integer on a 0-25 scale.
7. strengths/issues/suggestions should be concise English phrases.

Original title:
{title}

Original essay:
{text}
""".strip()

SUBJECT_CONFIG = {
    "chinese": {
        "display_name": "语文作文",
        "pdf_title": "AI 语文作文批改报告",
        "score_max": 60,
        "review_prompt": CHINESE_REVIEW_PROMPT,
    },
    "english": {
        "display_name": "英语作文",
        "pdf_title": "AI English Essay Review",
        "score_max": 25,
        "review_prompt": ENGLISH_REVIEW_PROMPT,
    },
}


def ensure_cjk_font_registered() -> None:
    try:
        pdfmetrics.getFont("STSong-Light")
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


class EssayService:
    def __init__(self) -> None:
        self.oss_service = OssService()
        self.vision_ocr = VisionOcrService()

    def correct_asset(
        self,
        asset: Asset,
        subject: str = "chinese",
        raw_text: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        subject = self._normalize_subject(subject)
        source, recognized_title, recognized_text = self._resolve_essay_text(
            asset=asset,
            subject=subject,
            raw_text=raw_text,
            title=title,
        )
        if not recognized_text.strip():
            raise ValueError("未能识别到作文正文，请重新上传更清晰的截图")

        review = self._review_essay(subject=subject, title=recognized_title, text=recognized_text)
        corrected_text = review["corrected_text"].strip()
        if not corrected_text:
            raise ValueError("作文批改结果为空，请稍后重试")

        annotated_markup = self._build_revision_markup(
            original_text=recognized_text,
            corrected_text=corrected_text,
        )
        pdf_bytes = self._build_pdf_bytes(
            subject=subject,
            original_title=recognized_title,
            original_text=recognized_text,
            corrected_title=review.get("corrected_title") or recognized_title or "Writing Review",
            corrected_text=corrected_text,
            annotated_markup=annotated_markup,
            review=review,
        )

        return {
            "subject": subject,
            "source": source,
            "recognized_title": recognized_title,
            "recognized_text": recognized_text,
            "corrected_title": review.get("corrected_title") or recognized_title or "Writing Review",
            "corrected_title_cn": review.get("corrected_title_cn") or "",
            "corrected_text": corrected_text,
            "corrected_text_cn": review.get("corrected_text_cn") or "",
            "summary": review.get("summary", ""),
            "summary_cn": review.get("summary_cn") or "",
            "score": int(review.get("score", 0) or 0),
            "score_max": int(
                review.get("score_max", SUBJECT_CONFIG[subject]["score_max"])
                or SUBJECT_CONFIG[subject]["score_max"]
            ),
            "strengths": self._normalize_list(review.get("strengths")),
            "strengths_cn": self._normalize_list(review.get("strengths_cn")),
            "issues": self._normalize_list(review.get("issues")),
            "issues_cn": self._normalize_list(review.get("issues_cn")),
            "suggestions": self._normalize_list(review.get("suggestions")),
            "suggestions_cn": self._normalize_list(review.get("suggestions_cn")),
            "annotated_markup": annotated_markup,
            "pdf_bytes": pdf_bytes,
        }

    def _normalize_subject(self, subject: str | None) -> str:
        normalized = (subject or "chinese").strip().lower()
        if normalized not in SUBJECT_CONFIG:
            raise ValueError("unsupported essay subject")
        return normalized

    def _resolve_essay_text(
        self,
        asset: Asset,
        subject: str,
        raw_text: str | None,
        title: str | None,
    ) -> tuple[str, str, str]:
        if raw_text and raw_text.strip():
            return "raw_text", (title or "").strip(), raw_text.strip()

        mime_type = (asset.mime_type or "").lower()
        suffix = PurePosixPath(asset.object_key).suffix.lower()
        if not mime_type.startswith("image/") and suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("作文批改当前仅支持上传作文截图")

        image_bytes = self._download_asset_bytes(asset)
        if subject == "english":
            ocr_payload = self.vision_ocr.extract_english_essay_from_image_bytes(
                image_bytes=image_bytes,
                mime_type=mime_type or self._infer_mime_type_from_suffix(suffix),
            )
        else:
            ocr_payload = self.vision_ocr.extract_chinese_essay_from_image_bytes(
                image_bytes=image_bytes,
                mime_type=mime_type or self._infer_mime_type_from_suffix(suffix),
            )

        recognized_title = (title or ocr_payload.get("title") or "").strip()
        recognized_text = str(ocr_payload.get("text") or "").strip()
        return "vision_ocr", recognized_title, recognized_text

    def _review_essay(self, subject: str, title: str, text: str) -> dict[str, Any]:
        prompt = SUBJECT_CONFIG[subject]["review_prompt"].format(
            title=title or "(untitled)",
            text=text,
        )
        if subject == "chinese":
            prompt += """

补充要求：
1. 这次不是基础纠错，而是深度润色。
2. 请把作文提升到“高分考场作文”的完成度，而不是只改几个词。
3. 在不改变原文核心事件、立意和情感走向的前提下，主动优化：
   - 开头吸引力
   - 段落过渡
   - 细节描写
   - 心理描写
   - 环境描写
   - 结尾升华
4. 可以适度补强动作、神态、声音、光影、触感等细节，让文章更有画面感。
5. 语言要更细腻、更流畅、更有文采，但不能空泛堆砌辞藻。
6. corrected_text 必须明显强于原文，篇章完整度和描写层次都要提升。
""".strip()
        elif subject == "english":
            prompt += """

Additional requirements:
1. This should be a deep polish, not only minor wording fixes.
2. Strengthen the hook, transitions, details, sentence rhythm, and ending.
3. Add vivid but natural description when helpful.
4. Preserve the original topic, events, and intended meaning.
5. The revised essay should read like a strong exam essay, not a stiff textbook answer.
""".strip()
        timeout = max(settings.essay_review_timeout_seconds, settings.ocr_timeout_seconds, 120)
        attempts = max(settings.essay_retry_count, 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                raw_output = call_openai_text_json(
                    client=get_openai_client(),
                    model=settings.openai_model_name,
                    prompt=prompt,
                    timeout=timeout,
                )
                break
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "timed out" not in message and "timeout" not in message:
                    raise
        else:
            raise RuntimeError("作文批改请求超时，请稍后重试或补充作文原文。") from last_error

        payload = self._parse_json_payload(raw_output)
        return {
            "corrected_title": str(payload.get("corrected_title", "")).strip(),
            "corrected_title_cn": str(payload.get("corrected_title_cn", "")).strip(),
            "corrected_text": str(payload.get("corrected_text", "")).strip(),
            "corrected_text_cn": str(payload.get("corrected_text_cn", "")).strip(),
            "summary": str(payload.get("summary", "")).strip(),
            "summary_cn": str(payload.get("summary_cn", "")).strip(),
            "score": payload.get("score", SUBJECT_CONFIG[subject]["score_max"] - 5),
            "score_max": payload.get("score_max", SUBJECT_CONFIG[subject]["score_max"]),
            "strengths": self._normalize_list(payload.get("strengths")),
            "strengths_cn": self._normalize_list(payload.get("strengths_cn")),
            "issues": self._normalize_list(payload.get("issues")),
            "issues_cn": self._normalize_list(payload.get("issues_cn")),
            "suggestions": self._normalize_list(payload.get("suggestions")),
            "suggestions_cn": self._normalize_list(payload.get("suggestions_cn")),
        }

    def _build_revision_markup(self, original_text: str, corrected_text: str) -> str:
        matcher = SequenceMatcher(a=original_text, b=corrected_text)
        parts: list[str] = []
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            old_chunk = original_text[a0:a1]
            new_chunk = corrected_text[b0:b1]
            if opcode == "equal":
                parts.append(self._paragraphize_text(old_chunk))
            elif opcode == "delete":
                parts.append(f'<strike>{self._paragraphize_text(old_chunk)}</strike>')
            elif opcode == "insert":
                parts.append(f'<font color="red"><super>{self._paragraphize_text(new_chunk)}</super></font>')
            elif opcode == "replace":
                parts.append(
                    f'<font color="red"><super>{self._paragraphize_text(new_chunk)}</super></font>'
                    f'<strike>{self._paragraphize_text(old_chunk)}</strike>'
                )
        return "".join(parts)

    def _build_pdf_bytes(
        self,
        subject: str,
        original_title: str,
        original_text: str,
        corrected_title: str,
        corrected_text: str,
        annotated_markup: str,
        review: dict[str, Any],
    ) -> bytes:
        ensure_cjk_font_registered()
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "EssayBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=12,
            leading=20,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1f2937"),
        )
        heading_style = ParagraphStyle(
            "EssayHeading",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=16,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
        title_style = ParagraphStyle(
            "EssayTitle",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "EssayMeta",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#475569"),
        )

        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        doc = SimpleDocTemplate(
            temp_path,
            pagesize=A4,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
        )

        score_line = (
            f"{int(review.get('score', 0) or 0)}/"
            f"{int(review.get('score_max', SUBJECT_CONFIG[subject]['score_max']) or SUBJECT_CONFIG[subject]['score_max'])}"
        )
        story = [
            Paragraph(SUBJECT_CONFIG[subject]["pdf_title"], title_style),
            Spacer(1, 6),
            Paragraph(
                f"Subject: {escape(SUBJECT_CONFIG[subject]['display_name'])}<br/>"
                f"Original Title: {escape(original_title or 'Untitled')}<br/>"
                f"Revised Title: {escape(corrected_title or 'Writing Review')}<br/>"
                f"Score: {score_line}",
                meta_style,
            ),
            Spacer(1, 12),
            Paragraph("1. OCR Text", heading_style),
            Paragraph(self._paragraphize_text(original_text), body_style),
            Spacer(1, 12),
            Paragraph("2. Revision Markup", heading_style),
            Paragraph(annotated_markup, body_style),
            Spacer(1, 12),
            Paragraph("3. Revised Essay", heading_style),
            Paragraph(self._paragraphize_text(corrected_text), body_style),
            Spacer(1, 12),
        ]

        if subject == "english" and str(review.get("corrected_text_cn") or "").strip():
            story.extend(
                [
                    Paragraph("4. Chinese Parallel Translation", heading_style),
                    Paragraph(self._paragraphize_text(str(review.get("corrected_text_cn") or "")), body_style),
                    Spacer(1, 12),
                ]
            )

        story.extend(
            [
            Paragraph("5. Feedback", heading_style),
            Paragraph(self._paragraphize_text(str(review.get("summary", "") or "No feedback")), body_style),
            ]
        )

        if subject == "english" and str(review.get("summary_cn") or "").strip():
            story.extend(
                [
                    Spacer(1, 8),
                    Paragraph("中文点评", heading_style),
                    Paragraph(self._paragraphize_text(str(review.get("summary_cn") or "")), body_style),
                ]
            )

        story.extend(
            [
            Spacer(1, 8),
            Paragraph("Strengths: " + self._join_items(review.get("strengths")), meta_style),
            Paragraph("Issues: " + self._join_items(review.get("issues")), meta_style),
            Paragraph("Suggestions: " + self._join_items(review.get("suggestions")), meta_style),
            ]
        )

        if subject == "english":
            story.extend(
                [
                    Spacer(1, 8),
                    Paragraph("优点： " + self._join_items(review.get("strengths_cn")), meta_style),
                    Paragraph("问题： " + self._join_items(review.get("issues_cn")), meta_style),
                    Paragraph("建议： " + self._join_items(review.get("suggestions_cn")), meta_style),
                ]
            )
        doc.build(story)
        try:
            with open(temp_path, "rb") as handle:
                return handle.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _download_asset_bytes(self, asset: Asset) -> bytes:
        url = self.oss_service.public_url(asset.object_key)
        with httpx.Client(timeout=45) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def download_asset_bytes(self, asset: Asset) -> bytes:
        return self._download_asset_bytes(asset)

    def _infer_mime_type_from_suffix(self, suffix: str) -> str:
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _normalize_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

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
                raise
            return json.loads(match.group(0))

    def _paragraphize_text(self, text: str) -> str:
        normalized = escape(text or "")
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.replace("\n", "<br/>")

    def _join_items(self, items: Any) -> str:
        normalized = self._normalize_list(items)
        if not normalized:
            return "None"
        return "; ".join(normalized)
