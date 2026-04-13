from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


def call_gemini_text(model: str, prompt: str, max_output_tokens: int, temperature: float = 0.4) -> str:
    api_key = (settings.gaokao_gemini_api_key or settings.gemini_api_key).strip()
    if not api_key:
        raise ValueError("Gemini 未配置可用的 API Key")

    last_error: Exception | None = None
    for candidate_model in gemini_candidate_models(model):
        for _ in range(2):
            try:
                return _call_single_gemini(
                    api_key=api_key,
                    model=candidate_model,
                    prompt=prompt,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                last_error = exc
                if not is_retryable_gemini_error(exc):
                    raise
    raise last_error or ValueError("Gemini 调用失败")


def call_gemini_text_json(model: str, prompt: str, parser) -> dict[str, Any]:
    text = call_gemini_text(model=model, prompt=prompt, max_output_tokens=900, temperature=0.5)
    if not text.strip():
        raise ValueError("Gemini 未返回可解析的文本")
    try:
        return parser(text)
    except Exception:
        return parse_gemini_section_payload(text)


def parse_gemini_section_payload(raw_text: str) -> dict[str, Any]:
    sections: dict[str, list[str]] = {}
    current_section = ""
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":") and line[:-1] in {"SUMMARY", "ADVISOR", "SCHOOL_LOGIC", "MAJOR", "DEEP", "NOTES"}:
            current_section = line[:-1]
            sections.setdefault(current_section, [])
            continue
        if current_section:
            sections.setdefault(current_section, []).append(line)

    recommendation_notes: list[dict[str, str]] = []
    for line in sections.get("NOTES", []):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            continue
        school, major, reason, major_comment = parts
        if school and major:
            recommendation_notes.append(
                {
                    "school": school,
                    "major": major,
                    "reason": reason,
                    "major_comment": major_comment,
                }
            )

    def normalize_bullets(items: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in items:
            text = item.lstrip("-• ").strip()
            if text:
                normalized.append(text)
        return normalized

    summary = " ".join(sections.get("SUMMARY", [])).strip()
    if not summary:
        raise ValueError("Gemini 未返回可解析的顾问内容")

    return {
        "summary": summary,
        "advisor_takeaways": normalize_bullets(sections.get("ADVISOR", [])),
        "school_choice_logic": normalize_bullets(sections.get("SCHOOL_LOGIC", [])),
        "major_observations": normalize_bullets(sections.get("MAJOR", [])),
        "deep_analysis": normalize_bullets(sections.get("DEEP", [])),
        "recommendation_notes": recommendation_notes,
    }


def gemini_candidate_models(model: str) -> list[str]:
    candidates = [model]
    fallback_map = {
        "gemini-2.5-flash": ["gemini-2.0-flash"],
        "gemini-2.5-flash-lite": ["gemini-2.0-flash"],
        "gemini-2.5-pro": ["gemini-2.5-flash", "gemini-2.0-flash"],
    }
    for fallback in fallback_map.get(model, []):
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates


def is_retryable_gemini_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ["503", "service unavailable", "timeout", "timed out", "temporarily unavailable"])


def _call_single_gemini(
    api_key: str,
    model: str,
    prompt: str,
    max_output_tokens: int,
    temperature: float,
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    with httpx.Client(timeout=settings.gaokao_llm_timeout_seconds) as client:
        response = client.post(url, params={"key": api_key}, json=payload)
        response.raise_for_status()
        response_json = response.json()

    candidates = response_json.get("candidates") or []
    first_candidate = candidates[0] if candidates else {}
    content = first_candidate.get("content") or {}
    parts = content.get("parts") or []
    text = ""
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            text += str(part["text"])
    if not text.strip():
        raise ValueError("Gemini 未返回可解析的文本")
    return text
