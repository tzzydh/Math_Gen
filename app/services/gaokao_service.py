from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.gaokao_admission_baseline import GaokaoAdmissionBaseline
from app.db.models.gaokao_control_line import GaokaoControlLine
from app.db.models.gaokao_score_rank import GaokaoScoreRank
from app.schemas.gaokao import GaokaoConsultationRequest, GaokaoPlanRequest
from core.openai_compat import call_openai_text_json


YEAR = 2025
PROVINCE = "吉林省"
ROOT_DIR = Path(__file__).resolve().parents[2]
DIRECTION_POOL_PATH = ROOT_DIR / "data" / "gaokao" / "processed" / "jilin_2025_direction_pool.json"

TRACK_LABELS = {
    "physics": "物理类",
    "history": "历史类",
}

BUCKET_LABELS = {
    "chong": "冲",
    "wen": "稳",
    "bao": "保",
}

DEFAULT_BUCKET_COUNTS = {
    "chong": 4,
    "wen": 4,
    "bao": 4,
}

EXTENDED_GROUP_PRIORITY = {
    "数据锚定补强池": 0,
    "方向扩展关注池": 1,
    "上限参考池": 2,
}

DIRECTION_ALIAS_MAP = {
    "electronic_info": [
        "电子信息",
        "电子",
        "通信",
        "自动化",
        "电气",
        "物联网",
        "计算机",
        "软件",
        "大数据",
        "数据科学",
        "信息管理",
        "人工智能",
        "芯片",
        "微电子",
        "数智",
    ]
}

GAOKAO_REPORT_PROMPT = """
你是一名非常擅长中国高考志愿规划的资深顾问。现在系统已经基于吉林省公开数据与规则引擎，生成了一份初步志愿方案。
你的任务不是推翻规则结果，而是在规则结论基础上做更细的顾问分析和润色，让报告更像真人顾问。

请严格输出 JSON，格式如下：
{{
  "summary": "更完整、更像真人顾问的总评",
  "advisor_takeaways": ["3-5条顾问结论"],
  "school_choice_logic": ["3-5条择校逻辑"],
  "major_observations": ["3-5条专业提醒"],
  "deep_analysis": ["3-6条更深的顾问分析"],
  "strategy": ["3-5条填报策略"],
  "risk_notes": ["3-5条风险提醒"],
  "execution_checklist": ["3-5条执行清单"]
}}

要求：
1. 必须保留“张雪峰式”的现实、直接、面向普通家庭的判断风格，但不要攻击性表达。
2. 不要编造学校、专业、分数线、位次。
3. 必须围绕系统给出的规则结论展开，不要脱离输入信息空谈。
4. 语言要具体，避免每次都像模板；要针对分数、位次、专业偏好、城市偏好、预算、职业倾向给出差异化判断。
5. 只输出 JSON。

用户输入：
{user_payload}

规则引擎结论：
{rule_payload}
""".strip()

GAOKAO_GEMINI_ADVISOR_PROMPT = """
你是一名中国高考志愿顾问。系统已经基于吉林省公开数据和本地规则，完成了分数定位、位次换算、冲稳保分层、学校池筛选和基础策略判断。

你的任务不是重算数据，而是补上“顾问味道”和“推荐院校的细点评”。
请务必精炼，整份输出控制在较短篇幅，避免长段空话。

请严格按下面格式输出纯文本，不要输出 markdown，不要输出 JSON，不要输出额外说明：

SUMMARY:
一句 60-100 字总评

ADVISOR:
- 结论1
- 结论2
- 结论3

SCHOOL_LOGIC:
- 逻辑1
- 逻辑2

MAJOR:
- 提醒1
- 提醒2

DEEP:
- 深度判断1
- 深度判断2

NOTES:
学校名|专业名|推荐理由|专业提醒
学校名|专业名|推荐理由|专业提醒

要求：
1. 不要改动分数、位次、控制线、冲稳保结论，也不要重新发明学校。
2. NOTES 只允许引用系统已经给出的前 4 个学校和专业；拿不准就留空。
3. recommendation 的推荐理由和专业提醒各控制在 20-35 字。
4. strategy、risk_notes、execution_checklist 由本地规则负责，你不要生成。
5. 语气要像资深志愿顾问，明确、现实、有判断，不要空泛鸡汤。
6. 结合用户的专业偏好、城市偏好、职业倾向、预算和补充说明做个性化判断。

用户输入：
{user_payload}

规则引擎结果：
{rule_payload}
""".strip()

GAOKAO_GEMINI_SUMMARY_PROMPT = """
你是一名中国高考志愿顾问。请基于下面的用户信息和规则结果，只输出 4 行纯文本，不要输出其他内容：

SUMMARY: 一句 50-80 字总评
TAKEAWAY: 一句 20-40 字关键判断
TAKEAWAY: 一句 20-40 字关键判断
DEEP: 一句 20-40 字更深的提醒

要求：
1. 现实、直接、像真人顾问，不要鸡汤。
2. 不要改动分数、位次、院校和规则结论。
3. 只做顾问分析，不要重写整份报告。

用户输入：
{user_payload}

规则结果：
{rule_payload}
""".strip()

GAOKAO_GEMINI_NOTES_PROMPT = """
你是一名中国高考志愿顾问。请只针对下面给出的推荐项，补充更像真人顾问的一句推荐理由和一句专业提醒。

请严格按下面格式输出纯文本，每行一条，不要输出其他内容：
学校名|专业名|推荐理由|专业提醒

要求：
1. 只允许使用输入里已经出现的学校和专业，不能编造。
2. 最多输出 4 行。
3. 每条推荐理由和专业提醒都控制在 18-32 字。
4. 如果拿不准，可以少输出几行，但不要输出解释。

用户输入：
{user_payload}

推荐项：
{recommendation_payload}
""".strip()


@lru_cache(maxsize=1)
def load_jilin_direction_pool() -> list[dict[str, Any]]:
    if not DIRECTION_POOL_PATH.exists():
        return []
    try:
        return json.loads(DIRECTION_POOL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


class GaokaoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_consultation(self, payload: GaokaoConsultationRequest) -> dict[str, Any]:
        province = self._normalize_province(payload.province)
        if province != PROVINCE:
            raise ValueError("当前高考数据版只支持吉林省")

        score = self._safe_parse_int(payload.score)
        rank = self._safe_parse_int(payload.rank)
        track = self._safe_infer_track(payload.subject_combination)

        quick_judgment: list[str] = []
        if score is not None:
            quick_judgment.append(f"先把位置说清楚：你现在是 {score} 分。吉林省报考先看位次，再看学校。")
        else:
            quick_judgment.append("你连分数都没告诉我，我现在给你任何学校建议都不负责任。先把分数说清楚。")

        if rank is not None:
            quick_judgment.append(f"你已经提供了位次 {rank}，这个信息比单纯分数更值钱。")
        elif score is not None and track:
            inferred_rank = self._lookup_rank(track, score)
            if inferred_rank is not None:
                quick_judgment.append(f"按吉林省 {TRACK_LABELS[track]} 公开数据，{score} 分大约在第 {inferred_rank} 名。")

        if track == "physics":
            quick_judgment.append("物理类最大的优势是专业出口更宽，所以后面别先问学校，先问专业值不值得。")
        elif track == "history":
            quick_judgment.append("历史类不能只看学校名头，很多专业名字体面，但就业出口并不一定体面。")
        else:
            quick_judgment.append("你连选科都没说，我没法判断你是物理类还是历史类，这会直接影响方向判断。")

        questions = self._build_consult_questions(payload, score=score, rank=rank, track=track)
        readiness = "ready" if len([q for q in questions if q["required"]]) == 0 else "need_more_info"
        opening = self._build_consult_opening(payload, score=score, rank=rank, track=track)
        next_step = (
            "你的关键信息已经差不多齐了，可以直接生成最终方案。"
            if readiness == "ready"
            else "先把上面的关键问题补齐，我再给你做最后的志愿方案。"
        )

        return {
            "readiness": readiness,
            "opening": opening,
            "inferred_track": track,
            "quick_judgment": quick_judgment[:4],
            "questions": questions,
            "next_step": next_step,
        }

    def build_plan(self, payload: GaokaoPlanRequest) -> dict[str, Any]:
        province = self._normalize_province(payload.province)
        if province != PROVINCE:
            raise ValueError("当前高考数据版只支持吉林省")

        advisor_mode = self._normalize_advisor_mode(payload.advisor_mode)
        advisor_provider = self._resolve_advisor_provider(payload.advisor_provider)
        advisor_model = self._resolve_advisor_model(
            provider=advisor_provider,
            model_value=payload.advisor_model,
        )
        score = self._parse_positive_int(payload.score, "分数")
        track = self._infer_track(payload.subject_combination)
        control_lines = self._get_control_lines(track)
        calculated_rank = self._resolve_rank(track=track, score=score, raw_rank=payload.rank)
        baselines = self._get_baselines(track)
        if not baselines:
            raise ValueError("吉林省公开录取基线尚未导入")

        recommendations = self._build_recommendations(
            payload=payload,
            track=track,
            score=score,
            rank=calculated_rank,
            baselines=baselines,
        )
        if not recommendations:
            recommendations = self._build_fallback_recommendations(baselines, score, calculated_rank, payload)

        direction_cards = self._build_direction_cards(payload, track, score, calculated_rank, control_lines)
        direction_advice = [card["content"] for card in direction_cards]
        major_breakdown = self._build_major_breakdown(payload, track, score, calculated_rank)
        signature_advice = self._build_signature_advice(payload, track, score, calculated_rank, recommendations)
        extended_pool = self._build_extended_pool(payload, track, score, calculated_rank, recommendations)
        school_pool_note = self._build_school_pool_note(payload, extended_pool)
        advisor_takeaways = self._build_advisor_takeaways(payload, track, score, calculated_rank, recommendations)
        school_choice_logic = self._build_school_choice_logic(payload, track, calculated_rank, recommendations)
        major_observations = self._build_major_observations(payload, track, recommendations)
        strategy = self._build_strategy(payload, track, score, calculated_rank, control_lines)
        risk_notes = self._build_risk_notes(payload, track, score, calculated_rank, control_lines, recommendations)
        execution_checklist = self._build_execution_checklist(payload, recommendations)
        summary = self._build_summary(track, score, calculated_rank, control_lines, recommendations)
        deep_analysis: list[str] = []
        llm_enhanced = False
        advisor_engine_note = "当前报告由规则引擎直接生成。"
        attempted_advisor_provider = advisor_provider if advisor_mode != "rules_only" else None
        attempted_advisor_model = advisor_model if advisor_mode != "rules_only" else None

        rule_payload = {
            "summary": summary,
            "advisor_takeaways": advisor_takeaways,
            "school_choice_logic": school_choice_logic,
            "major_observations": major_observations,
            "strategy": strategy,
            "risk_notes": risk_notes,
            "execution_checklist": execution_checklist,
            "recommendations": recommendations[:8],
            "major_breakdown": major_breakdown,
            "signature_advice": signature_advice,
            "extended_pool_preview": extended_pool[:8],
            "school_pool_note": school_pool_note,
            "direction_cards": direction_cards,
            "control_lines": [
                {"line_type": line.line_type, "score": line.score}
                for line in control_lines
            ],
        }

        if advisor_mode != "rules_only":
            llm_payload, llm_failure_reason = self._enhance_report_with_llm(
                payload=payload,
                track=track,
                score=score,
                rank=calculated_rank,
                advisor_provider=advisor_provider,
                advisor_model=advisor_model,
                rule_payload=rule_payload,
            )
            if llm_payload:
                summary = llm_payload.get("summary") or summary
                advisor_takeaways = llm_payload.get("advisor_takeaways") or advisor_takeaways
                school_choice_logic = llm_payload.get("school_choice_logic") or school_choice_logic
                major_observations = llm_payload.get("major_observations") or major_observations
                deep_analysis = llm_payload.get("deep_analysis") or []
                strategy = llm_payload.get("strategy") or strategy
                risk_notes = llm_payload.get("risk_notes") or risk_notes
                execution_checklist = llm_payload.get("execution_checklist") or execution_checklist
                recommendations = self._apply_recommendation_notes(
                    recommendations,
                    llm_payload.get("recommendation_notes"),
                )
                llm_enhanced = True
                advisor_engine_note = (
                    f"本次先由吉林数据规则引擎做硬判断，再使用 {self._provider_label(advisor_provider)} "
                    f"的 {advisor_model} 做顾问润色与深度分析。"
                )
            else:
                advisor_mode = "rules_only"
                reason_text = f" 原因：{llm_failure_reason}" if llm_failure_reason else ""
                advisor_engine_note = (
                    f"本次尝试使用 {self._provider_label(advisor_provider)} 的 {advisor_model} 做深度顾问分析，但模型增强未成功，"
                    f"已自动回退到纯规则模式。{reason_text}"
                )

        return {
            "year": YEAR,
            "track": track,
            "calculated_rank": calculated_rank,
            "summary": summary,
            "advisor_mode": advisor_mode,
            "advisor_provider": attempted_advisor_provider,
            "advisor_model": attempted_advisor_model,
            "llm_enhanced": llm_enhanced,
            "advisor_engine_note": advisor_engine_note,
            "direction_advice": direction_advice,
            "direction_cards": direction_cards,
            "advisor_takeaways": advisor_takeaways,
            "school_choice_logic": school_choice_logic,
            "major_observations": major_observations,
            "major_breakdown": major_breakdown,
            "signature_advice": signature_advice,
            "school_pool_note": school_pool_note,
            "extended_pool": extended_pool,
            "deep_analysis": deep_analysis,
            "strategy": strategy,
            "risk_notes": risk_notes,
            "execution_checklist": execution_checklist,
            "control_lines": [
                {"line_type": line.line_type, "score": line.score}
                for line in control_lines
            ],
            "recommendations": recommendations,
            "raw_output": None,
        }

    def _build_consult_opening(
        self,
        payload: GaokaoConsultationRequest,
        score: int | None,
        rank: int | None,
        track: str | None,
    ) -> str:
        if score is None:
            return "我先不急着给学校名单。你得先把分数、选科、家里能承受什么、你想去哪儿，这些最基本的信息说清楚。"
        if track == "physics":
            return (
                f"你现在这档大概是吉林物理类 {score} 分。先别急着冲学校，"
                "我更想先问清楚你到底是想保就业、冲城市，还是死守某个专业。"
            )
        if track == "history":
            return (
                f"你现在这档大概是吉林历史类 {score} 分。历史类最怕选到名字好听、出口模糊的专业，"
                "所以我得先把你的职业倾向问透。"
            )
        return "我先把你的情况问透，再给结论。志愿填报最怕的是问题没问清楚，答案已经给出去了。"

    def _normalize_province(self, value: str) -> str:
        normalized = re.sub(r"\s+", "", value or "")
        if normalized in {"吉林", "吉林省"}:
            return PROVINCE
        return value.strip()

    def _safe_parse_int(self, value: str | None) -> int | None:
        if not value or not value.strip():
            return None
        matched = re.findall(r"\d+", value)
        if not matched:
            return None
        return int(matched[0])

    def _parse_positive_int(self, value: str | None, field_name: str) -> int:
        matched = re.findall(r"\d+", value or "")
        if not matched:
            raise ValueError(f"{field_name}格式不正确")
        return int(matched[0])

    def _safe_infer_track(self, subject_combination: str | None) -> str | None:
        if not subject_combination:
            return None
        normalized = subject_combination.replace(" ", "")
        if "史" in normalized:
            return "history"
        if "物" in normalized:
            return "physics"
        return None

    def _infer_track(self, subject_combination: str) -> str:
        normalized = (subject_combination or "").replace(" ", "")
        if "史" in normalized:
            return "history"
        if "物" in normalized:
            return "physics"
        raise ValueError("暂时只支持吉林省新高考物理类或历史类组合")

    def _resolve_rank(self, track: str, score: int, raw_rank: str | None) -> int:
        parsed_rank = self._safe_parse_int(raw_rank)
        if parsed_rank is not None:
            return parsed_rank

        rank = self.db.scalar(
            select(GaokaoScoreRank.rank).where(
                GaokaoScoreRank.year == YEAR,
                GaokaoScoreRank.province == PROVINCE,
                GaokaoScoreRank.track == track,
                GaokaoScoreRank.score == score,
            )
        )
        if rank is None:
            raise ValueError("未找到对应分数的吉林省位次，请手动填写位次")
        return int(rank)

    def _lookup_rank(self, track: str, score: int) -> int | None:
        rank = self.db.scalar(
            select(GaokaoScoreRank.rank).where(
                GaokaoScoreRank.year == YEAR,
                GaokaoScoreRank.province == PROVINCE,
                GaokaoScoreRank.track == track,
                GaokaoScoreRank.score == score,
            )
        )
        return int(rank) if rank is not None else None

    def _normalize_advisor_mode(self, value: str | None) -> str:
        normalized = (value or "hybrid").strip().lower()
        if normalized not in {"hybrid", "rules_only"}:
            return "hybrid"
        return normalized

    def _resolve_advisor_provider(self, value: str | None) -> str:
        provider = (value or settings.gaokao_default_provider or "gemini").strip().lower()
        if provider not in {"glm", "openai", "gemini"}:
            return "gemini"
        return provider

    def _resolve_advisor_model(self, provider: str, model_value: str | None) -> str:
        model = (model_value or "").strip()
        if model:
            return model
        if provider == "openai":
            default_model = (
                settings.gaokao_openai_default_model
                or settings.gaokao_default_model
                or "gpt-4o-mini"
            ).strip()
            return default_model or "gpt-4o-mini"
        if provider == "gemini":
            default_model = (
                settings.gaokao_gemini_default_model
                or settings.gemini_model_name
                or settings.gaokao_default_model
                or "gemini-2.5-flash"
            ).strip()
            return default_model or "gemini-2.5-flash"
        default_model = (
            settings.gaokao_glm_default_model
            or settings.gaokao_default_model
            or settings.openai_model_name
        ).strip()
        return default_model or settings.openai_model_name

    def _provider_label(self, provider: str | None) -> str:
        labels = {
            "gemini": "Gemini",
            "glm": "GLM / 智谱兼容接口",
            "openai": "OpenAI",
        }
        return labels.get(provider or "", provider or "默认供应商")

    def _build_advisor_client(self, provider: str) -> OpenAI:
        if provider == "gemini":
            raise ValueError("Gemini provider uses a dedicated client path")
        if provider == "openai":
            api_key = settings.gaokao_openai_api_key.strip()
            base_url = (settings.gaokao_openai_base_url or "https://api.openai.com/v1").strip()
        else:
            api_key = (settings.gaokao_glm_api_key or settings.openai_api_key).strip()
            base_url = (settings.gaokao_glm_base_url or settings.openai_base_url).strip()

        if not api_key:
            raise ValueError(f"{self._provider_label(provider)} 未配置可用的 API Key")
        if not base_url:
            raise ValueError(f"{self._provider_label(provider)} 未配置可用的 Base URL")
        return OpenAI(api_key=api_key, base_url=base_url)

    def _call_gemini_text_json(self, model: str, prompt: str) -> dict[str, Any]:
        api_key = (settings.gaokao_gemini_api_key or settings.gemini_api_key).strip()
        if not api_key:
            raise ValueError("Gemini 未配置可用的 API Key")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 900,
            },
        }
        with httpx.Client(timeout=settings.gaokao_llm_timeout_seconds) as client:
            response = client.post(
                url,
                params={"key": api_key},
                json=payload,
            )
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

        try:
            return self._parse_json_payload(text)
        except Exception:
            return self._parse_gemini_section_payload(text)

    def _call_gemini_text(self, model: str, prompt: str, max_output_tokens: int) -> str:
        api_key = (settings.gaokao_gemini_api_key or settings.gemini_api_key).strip()
        if not api_key:
            raise ValueError("Gemini 未配置可用的 API Key")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
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
        return text.strip()

    def _apply_recommendation_notes(
        self,
        recommendations: list[dict[str, Any]],
        recommendation_notes: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if not recommendation_notes:
            return recommendations

        note_map: dict[tuple[str, str], dict[str, Any]] = {}
        for item in recommendation_notes:
            if not isinstance(item, dict):
                continue
            school = str(item.get("school", "")).strip()
            major = str(item.get("major", "")).strip()
            if not school or not major:
                continue
            note_map[(school, major)] = item

        updated: list[dict[str, Any]] = []
        for rec in recommendations:
            key = (str(rec.get("school", "")).strip(), str(rec.get("major", "")).strip())
            note = note_map.get(key)
            if not note:
                updated.append(rec)
                continue
            merged = dict(rec)
            reason = str(note.get("reason", "")).strip()
            major_comment = str(note.get("major_comment", "")).strip()
            if reason:
                merged["reason"] = reason
            if major_comment:
                merged["major_comment"] = major_comment
            updated.append(merged)
        return updated

    def _parse_gemini_summary_lines(self, raw_text: str) -> dict[str, Any]:
        summary = ""
        takeaways: list[str] = []
        deep_analysis: list[str] = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif line.startswith("TAKEAWAY:"):
                text = line.split(":", 1)[1].strip()
                if text:
                    takeaways.append(text)
            elif line.startswith("DEEP:"):
                text = line.split(":", 1)[1].strip()
                if text:
                    deep_analysis.append(text)
        if not summary:
            raise ValueError("Gemini 未返回可解析的顾问总结")
        return {
            "summary": summary,
            "advisor_takeaways": takeaways,
            "deep_analysis": deep_analysis,
        }

    def _parse_gemini_recommendation_lines(self, raw_text: str) -> list[dict[str, str]]:
        notes: list[dict[str, str]] = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or "|" not in line:
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 4:
                continue
            school, major, reason, major_comment = parts
            if not school or not major:
                continue
            notes.append(
                {
                    "school": school,
                    "major": major,
                    "reason": reason,
                    "major_comment": major_comment,
                }
            )
        return notes

    def _enhance_report_with_llm(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        advisor_provider: str,
        advisor_model: str,
        rule_payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not settings.gaokao_enable_llm:
            return None, "系统已关闭模型增强"
        user_payload = {
            "province": payload.province,
            "score": score,
            "rank": rank,
            "track": TRACK_LABELS.get(track, track),
            "subject_combination": payload.subject_combination,
            "preferred_majors": payload.preferred_majors,
            "preferred_cities": payload.preferred_cities,
            "career_preferences": payload.career_preferences,
            "family_budget": payload.family_budget,
            "notes": payload.notes,
        }
        if advisor_provider == "gemini":
            compact_rule_payload = self._build_gemini_rule_payload(rule_payload)
            prompt = GAOKAO_GEMINI_ADVISOR_PROMPT.format(
                user_payload=self._to_json_text(user_payload),
                rule_payload=self._to_json_text(compact_rule_payload),
            )
            last_error: Exception | None = None
            for _ in range(2):
                try:
                    payload_json = self._call_gemini_text_json(advisor_model, prompt)
                    return {
                        "summary": str(payload_json.get("summary", "")).strip(),
                        "advisor_takeaways": self._normalize_text_list(payload_json.get("advisor_takeaways")),
                        "school_choice_logic": self._normalize_text_list(payload_json.get("school_choice_logic")),
                        "major_observations": self._normalize_text_list(payload_json.get("major_observations")),
                        "deep_analysis": self._normalize_text_list(payload_json.get("deep_analysis")),
                        "strategy": [],
                        "risk_notes": [],
                        "execution_checklist": [],
                        "recommendation_notes": payload_json.get("recommendation_notes"),
                    }, None
                except Exception as exc:
                    last_error = exc
            return None, self._summarize_llm_error(last_error or ValueError("Gemini 调用失败"), advisor_provider, advisor_model)

        prompt_rule_payload = (
            self._build_gemini_rule_payload(rule_payload)
            if advisor_provider == "gemini"
            else rule_payload
        )
        prompt_template = (
            GAOKAO_GEMINI_ADVISOR_PROMPT
            if advisor_provider == "gemini"
            else GAOKAO_REPORT_PROMPT
        )
        prompt = prompt_template.format(
            user_payload=self._to_json_text(user_payload),
            rule_payload=self._to_json_text(prompt_rule_payload),
        )
        try:
            if advisor_provider == "gemini":
                payload_json = self._call_gemini_text_json(advisor_model, prompt)
            else:
                raw_output = call_openai_text_json(
                    client=self._build_advisor_client(advisor_provider),
                    model=advisor_model,
                    prompt=prompt,
                    timeout=settings.gaokao_llm_timeout_seconds,
                )
                payload_json = self._parse_json_payload(raw_output)
        except Exception as exc:
            return None, self._summarize_llm_error(exc, advisor_provider, advisor_model)

        return {
            "summary": str(payload_json.get("summary", "")).strip(),
            "advisor_takeaways": self._normalize_text_list(payload_json.get("advisor_takeaways")),
            "school_choice_logic": self._normalize_text_list(payload_json.get("school_choice_logic")),
            "major_observations": self._normalize_text_list(payload_json.get("major_observations")),
            "deep_analysis": self._normalize_text_list(payload_json.get("deep_analysis")),
            "strategy": self._normalize_text_list(payload_json.get("strategy")),
            "risk_notes": self._normalize_text_list(payload_json.get("risk_notes")),
            "execution_checklist": self._normalize_text_list(payload_json.get("execution_checklist")),
            "recommendation_notes": payload_json.get("recommendation_notes"),
        }, None

    def _build_gemini_rule_payload(self, rule_payload: dict[str, Any]) -> dict[str, Any]:
        recommendations = []
        for item in rule_payload.get("recommendations", [])[:4]:
            if not isinstance(item, dict):
                continue
            recommendations.append(
                {
                    "school": item.get("school"),
                    "major": item.get("major"),
                    "city": item.get("city"),
                    "bucket": item.get("bucket"),
                    "school_level": item.get("school_level"),
                    "fit_score": item.get("fit_score"),
                    "decision_tags": item.get("decision_tags", []),
                    "min_score": item.get("min_score"),
                    "min_rank": item.get("min_rank"),
                }
            )

        return {
            "summary": rule_payload.get("summary"),
            "advisor_takeaways": rule_payload.get("advisor_takeaways", [])[:4],
            "school_choice_logic": rule_payload.get("school_choice_logic", [])[:4],
            "major_observations": rule_payload.get("major_observations", [])[:4],
            "signature_advice": rule_payload.get("signature_advice", [])[:4],
            "major_breakdown": rule_payload.get("major_breakdown", [])[:3],
            "direction_cards": rule_payload.get("direction_cards", [])[:3],
            "control_lines": rule_payload.get("control_lines", []),
            "recommendations": recommendations,
        }

    def _summarize_llm_error(self, exc: Exception, advisor_provider: str, advisor_model: str) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        lower_message = message.lower()
        if advisor_provider == "openai":
            base_url = (settings.gaokao_openai_base_url or "https://api.openai.com/v1").strip()
        elif advisor_provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com"
        else:
            base_url = (settings.gaokao_glm_base_url or settings.openai_base_url).strip()
        provider_label = self._provider_label(advisor_provider)

        if "503" in lower_message or "service unavailable" in lower_message:
            return f"{provider_label} 当前服务繁忙，顾问增强暂时不可用，系统已自动回退到规则模式"
        if "timed out" in lower_message or "timeout" in lower_message or "read operation timed out" in lower_message:
            return f"{provider_label} 响应超时，顾问增强暂时不可用，系统已自动回退到规则模式"
        if "connection" in lower_message and ("failed" in lower_message or "error" in lower_message):
            return f"{provider_label} 网络连接不稳定，顾问增强暂时不可用，系统已自动回退到规则模式"
        if "model" in lower_message and ("not found" in lower_message or "does not exist" in lower_message):
            return f"{provider_label} 的模型 {advisor_model} 在当前接口 {base_url} 下不可用"
        if "unsupported" in lower_message and "model" in lower_message:
            return f"{provider_label} 的模型 {advisor_model} 与当前接口 {base_url} 不兼容"
        if "401" in lower_message or "unauthorized" in lower_message or "invalid api key" in lower_message:
            return f"{provider_label} 鉴权失败，请检查 API Key"
        if "429" in lower_message or "quota" in lower_message or "rate limit" in lower_message:
            return f"{provider_label} 额度不足或触发限流"

        short_message = message.replace("\n", " ")
        if len(short_message) > 120:
            short_message = short_message[:117] + "..."
        return short_message

    def _normalize_text_list(self, value: Any) -> list[str]:
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
        match = re.search(r"\{.*\}", sanitized, flags=re.DOTALL)
        if match:
            sanitized = match.group(0)
        return json.loads(sanitized)

    def _parse_gemini_section_payload(self, raw_text: str) -> dict[str, Any]:
        sections: dict[str, list[str]] = {}
        current_section = ""
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.endswith(":") and line[:-1] in {
                "SUMMARY",
                "ADVISOR",
                "SCHOOL_LOGIC",
                "MAJOR",
                "DEEP",
                "NOTES",
            }:
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
            if not school or not major:
                continue
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
                text = re.sub(r"^[-•]\s*", "", item).strip()
                if text:
                    normalized.append(text)
            return normalized

        summary_lines = sections.get("SUMMARY", [])
        summary = " ".join(summary_lines).strip()
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

    def _to_json_text(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_consult_questions(
        self,
        payload: GaokaoConsultationRequest,
        score: int | None,
        rank: int | None,
        track: str | None,
    ) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        if score is None:
            questions.append(
                self._consult_question(
                    "score",
                    "score",
                    "先把分数说清楚",
                    "你家孩子今年大概多少分？这个不说明白，后面全是空谈。",
                    "分数是所有判断的起点，没有分数就没有位置。",
                    "例如：560",
                    ["520-540", "540-560", "560-580", "580+"],
                )
            )
        if not payload.subject_combination:
            questions.append(
                self._consult_question(
                    "subject",
                    "subjectCombination",
                    "选科组合必须先锁定",
                    "你到底是物理类还是历史类？别小看这个问题，这会直接决定整条路。",
                    "物理类和历史类不是一套推荐逻辑。",
                    "例如：物化生 / 史政地",
                    ["物化生", "物化地", "物生地", "史政地", "史地生"],
                )
            )
        if rank is None:
            questions.append(
                self._consult_question(
                    "rank",
                    "rank",
                    "位次最好也给我",
                    "如果你知道位次，直接告诉我。报考看位次，比看分数更硬。",
                    "同分人数、年份难度都会影响分数含金量，位次更稳定。",
                    "例如：12338",
                    ["按系统自动换算即可"],
                    required=False,
                )
            )

        if not payload.preferred_majors:
            title = "先说你想保什么"
            question = (
                "你更想保专业、保学校、还是保城市？如果专业还没想清楚，至少告诉我你是偏工科、偏医学、偏师范，还是偏财经法学。"
            )
            why = "张雪峰式问法里，这一步是灵魂追问。方向不清楚，冲稳保就会变成瞎填。"
            questions.append(
                self._consult_question(
                    "major",
                    "preferredMajors",
                    title,
                    question,
                    why,
                    "例如：计算机 / 临床医学 / 师范 / 法学 / 会计",
                    ["计算机", "电气自动化", "临床医学", "师范", "法学", "会计财经"],
                )
            )

        if not payload.preferred_cities:
            questions.append(
                self._consult_question(
                    "city",
                    "preferredCities",
                    "城市要不要优先",
                    "你能不能接受出省？你是想留东北，还是愿意去天津、北京、杭州、苏州这种资源更强的城市？",
                    "城市会直接决定实习机会、就业半径和未来生活成本。",
                    "例如：长春、沈阳、天津、杭州",
                    ["留吉林省内", "东北优先", "能接受省外", "优先北京天津杭州"],
                )
            )

        if not payload.career_preferences:
            question = "你更在意什么：稳定编制、好就业、高薪上限、读研深造，还是考公考编？"
            if track == "history":
                question = "历史类我一定要追问一句：你更偏向考编、考公、读研，还是直接就业？这个决定专业完全不一样。"
            questions.append(
                self._consult_question(
                    "career",
                    "careerPreferences",
                    "职业倾向必须问透",
                    question,
                    "同样一个分数，不同家庭和不同职业偏好，路径完全不是一回事。",
                    "例如：稳定编制 / 工程技术 / 金融 / 考公",
                    ["稳定编制", "工程技术", "高薪就业", "金融财经", "考公考编", "读研优先"],
                )
            )

        if not payload.family_budget:
            questions.append(
                self._consult_question(
                    "budget",
                    "familyBudget",
                    "家里能承受到哪一步",
                    "我得问一句现实的：家里预算大概是什么水平？能接受民办和中外合作，还是优先公办？",
                    "普通家庭做志愿，预算不是小问题，是底层约束。",
                    "例如：优先公办 / 可接受中外合作",
                    ["优先公办", "预算一般", "可接受中外合作", "学费不是主要问题"],
                )
            )

        if not payload.notes:
            questions.append(
                self._consult_question(
                    "notes",
                    "notes",
                    "最后补两个底线条件",
                    "能不能接受调剂？要不要优先双一流？有没有强烈不想去的城市或专业？",
                    "这些底线条件会直接决定最终方案能不能执行。",
                    "例如：能接受省外和调剂，优先双一流",
                    ["能接受调剂", "不接受调剂", "优先双一流", "不去太远城市"],
                    required=False,
                )
            )
        return questions[:6]

    def _consult_question(
        self,
        question_id: str,
        field: str,
        title: str,
        question: str,
        why: str,
        placeholder: str | None,
        suggested_options: list[str],
        required: bool = True,
    ) -> dict[str, Any]:
        return {
            "id": question_id,
            "field": field,
            "title": title,
            "question": question,
            "why": why,
            "placeholder": placeholder,
            "required": required,
            "suggested_options": suggested_options,
        }

    def _get_control_lines(self, track: str) -> list[GaokaoControlLine]:
        return list(
            self.db.scalars(
                select(GaokaoControlLine).where(
                    GaokaoControlLine.year == YEAR,
                    GaokaoControlLine.province == PROVINCE,
                    GaokaoControlLine.track == track,
                )
            )
        )

    def _get_baselines(self, track: str) -> list[GaokaoAdmissionBaseline]:
        return list(
            self.db.scalars(
                select(GaokaoAdmissionBaseline).where(
                    GaokaoAdmissionBaseline.data_year == YEAR,
                    GaokaoAdmissionBaseline.province == PROVINCE,
                    GaokaoAdmissionBaseline.track == track,
                )
            )
        )

    def _build_recommendations(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        baselines: list[GaokaoAdmissionBaseline],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        ranked_rows: list[dict[str, Any]] = []

        for baseline in baselines:
            if baseline.min_rank is None:
                continue

            rank_gap = self._rank_gap(rank, baseline.min_rank)
            score_gap = baseline.min_score - score
            bucket = self._classify_bucket(rank_gap, score_gap)
            if bucket is None:
                continue
            match_score, match_reasons, decision_tags = self._score_direction_match(payload, track, baseline)
            fit_score = self._fit_score(bucket, rank_gap, score_gap, match_score)
            row = {
                "school": baseline.school,
                "major": baseline.major,
                "city": baseline.city,
                "school_level": baseline.school_level,
                "bucket": bucket,
                "fit_score": fit_score,
                "risk_level": self._risk_level(bucket, rank_gap, score_gap),
                "reason": self._build_reason(rank, score, baseline, bucket, match_reasons),
                "major_comment": self._build_major_comment(payload, track, baseline, rank_gap, score_gap),
                "decision_tags": decision_tags,
                "data_year": baseline.data_year,
                "min_score": baseline.min_score,
                "min_rank": baseline.min_rank,
                "source_name": baseline.source_name,
                "_rank_gap": rank_gap,
                "_score_gap": score_gap,
            }
            grouped[bucket].append(row)
            ranked_rows.append(row)

        for bucket in grouped:
            grouped[bucket] = sorted(
                grouped[bucket],
                key=lambda item: (
                    -self._decision_priority(item["decision_tags"]),
                    -item["fit_score"],
                    abs(item["_rank_gap"]),
                    item["min_rank"] or math.inf,
                ),
            )

        selected: list[dict[str, Any]] = []
        used_keys: set[tuple[str, str, str]] = set()
        for bucket in ("wen", "bao", "chong"):
            count = DEFAULT_BUCKET_COUNTS[bucket]
            for item in grouped.get(bucket, [])[:count]:
                key = (item["school"], item["major"], item["bucket"])
                if key in used_keys:
                    continue
                used_keys.add(key)
                selected.append(item)

        if len(selected) < 10:
            for item in sorted(
                ranked_rows,
                key=lambda row: (
                    -self._decision_priority(row["decision_tags"]),
                    -row["fit_score"],
                    abs(row["_rank_gap"]),
                    row["min_rank"] or math.inf,
                ),
            ):
                key = (item["school"], item["major"], item["bucket"])
                if key in used_keys:
                    continue
                used_keys.add(key)
                selected.append(item)
                if len(selected) >= 12:
                    break

        for item in selected:
            item.pop("_rank_gap", None)
            item.pop("_score_gap", None)
        return selected

    def _decision_priority(self, tags: list[str]) -> int:
        primary = {"专业贴合", "职业导向", "城市贴合", "预算友好"}
        return sum(1 for tag in tags if tag in primary)

    def _build_fallback_recommendations(
        self,
        baselines: list[GaokaoAdmissionBaseline],
        score: int,
        rank: int,
        payload: GaokaoPlanRequest,
    ) -> list[dict[str, Any]]:
        sorted_rows = sorted(
            [item for item in baselines if item.min_rank is not None],
            key=lambda item: abs((item.min_rank or rank) - rank),
        )[:8]
        results = []
        for item in sorted_rows:
            _, match_reasons, decision_tags = self._score_direction_match(payload, item.track, item)
            rank_gap = self._rank_gap(rank, item.min_rank or rank)
            score_gap = item.min_score - score
            bucket = self._classify_bucket(rank_gap, score_gap)
            if bucket is None:
                continue
            results.append(
                {
                    "school": item.school,
                    "major": item.major,
                    "city": item.city,
                    "school_level": item.school_level,
                    "bucket": bucket,
                    "fit_score": self._fit_score(bucket, rank_gap, score_gap, 0),
                    "risk_level": self._risk_level(bucket, rank_gap, score_gap),
                    "reason": self._build_reason(rank, score, item, bucket, match_reasons),
                    "major_comment": self._build_major_comment(payload, item.track, item, rank_gap, score_gap),
                    "decision_tags": decision_tags,
                    "data_year": item.data_year,
                    "min_score": item.min_score,
                    "min_rank": item.min_rank,
                    "source_name": item.source_name,
                }
            )
        return results

    def _rank_gap(self, current_rank: int, baseline_rank: int) -> int:
        return baseline_rank - current_rank

    def _classify_bucket(self, rank_gap: int, score_gap: int) -> str | None:
        if rank_gap < -22000 or score_gap > 55:
            return None
        if rank_gap < -9000 or score_gap > 25:
            return "chong"
        if rank_gap < 12000 or score_gap > -30:
            return "wen"
        return "bao"

    def _score_direction_match(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        baseline: GaokaoAdmissionBaseline,
    ) -> tuple[int, list[str], list[str]]:
        score = 0
        reasons: list[str] = []
        tags: list[str] = []
        haystack = " ".join(
            [
                baseline.school,
                baseline.major,
                baseline.city,
                baseline.school_level or "",
                baseline.major_tags or "",
                baseline.notes or "",
            ]
        ).lower()

        major_pref = self._tokenize(payload.preferred_majors)
        city_pref = self._tokenize(payload.preferred_cities)
        career_pref = self._tokenize(payload.career_preferences)
        budget_pref = (payload.family_budget or "").strip()

        major_hits = [token for token in major_pref if token.lower() in haystack]
        if major_hits:
            score += 20
            reasons.append(f"命中意向专业关键词：{'、'.join(major_hits[:3])}")
            tags.append("专业贴合")
        elif major_pref and "electronic_info" in self._detect_direction_keys(payload, track):
            if not any(word in haystack for word in DIRECTION_ALIAS_MAP["electronic_info"]):
                score -= 24
                reasons.append("和电子信息主方向关联较弱，更适合作为保底兜底而不是主攻志愿")

        city_hits = [token for token in city_pref if token.lower() in baseline.city.lower()]
        if city_hits:
            score += 12
            reasons.append(f"符合城市偏好：{'、'.join(city_hits[:2])}")
            tags.append("城市贴合")

        career_map = {
            "稳定": ["师范", "医学", "会计", "法学", "教育", "电气"],
            "编制": ["师范", "教育", "医学", "会计"],
            "就业": ["计算机", "电气", "自动化", "会计", "护理", "电子"],
            "体制": ["师范", "法学", "会计", "医学"],
            "金融": ["金融", "会计", "财经"],
            "工科": ["工科", "计算机", "电子", "机械", "电气", "自动化"],
            "医生": ["医学", "临床", "口腔", "护理"],
        }
        for token in career_pref:
            for keyword, labels in career_map.items():
                if keyword in token and any(label in haystack for label in labels):
                    score += 10
                    reasons.append(f"和职业倾向“{token}”一致")
                    tags.append("职业导向")
                    break

        if track == "physics":
            physics_focus = DIRECTION_ALIAS_MAP["electronic_info"] if "electronic_info" in self._detect_direction_keys(payload, track) else ["计算机", "电气", "电子", "自动化", "机械", "医学"]
            if any(word in haystack for word in physics_focus):
                score += 6
                tags.append("物理类优势")
        if track == "history" and any(word in haystack for word in ["法学", "会计", "师范", "汉语", "新闻"]):
            score += 6
            tags.append("历史类优势")

        if budget_pref and any(word in budget_pref for word in ["公办", "低", "一般", "有限"]):
            if baseline.school_level and ("中外合作" in baseline.school_level or "民办" in baseline.school_level):
                score -= 16
                reasons.append("家庭预算偏谨慎，不建议优先中外合作或民办")
            else:
                tags.append("预算友好")

        if baseline.school_level and "双一流" in baseline.school_level:
            tags.append("层级亮点")

        tags = list(dict.fromkeys(tags))
        return score, reasons, tags[:4]

    def _tokenize(self, raw_text: str | None) -> list[str]:
        if not raw_text:
            return []
        return [token for token in re.split(r"[、,，/\\\s]+", raw_text) if token]

    def _fit_score(self, bucket: str, rank_gap: int, score_gap: int, match_score: int) -> int:
        base = {"chong": 73, "wen": 84, "bao": 80}[bucket]
        closeness = max(0, 20 - min(abs(rank_gap) // 600, 20))
        score_balance = max(-12, min(10, -score_gap // 4))
        return max(52, min(99, base + closeness + score_balance + match_score))

    def _risk_level(self, bucket: str, rank_gap: int, score_gap: int) -> str:
        if bucket == "bao":
            return "low"
        if bucket == "wen":
            return "medium"
        if rank_gap < -15000 or score_gap > 40:
            return "high"
        return "medium"

    def _build_reason(
        self,
        rank: int,
        score: int,
        baseline: GaokaoAdmissionBaseline,
        bucket: str,
        match_reasons: list[str],
    ) -> str:
        pieces = [
            f"{baseline.data_year}年吉林{TRACK_LABELS[baseline.track]}最低录取分为{baseline.min_score}分",
        ]
        if baseline.min_rank:
            pieces.append(f"最低位次约{baseline.min_rank}名，你当前位次约{rank}名")
        if baseline.min_score != score:
            pieces.append(f"分数差约{baseline.min_score - score:+d}分")
        pieces.append(f"按当前公开数据属于“{BUCKET_LABELS[bucket]}”档")
        if match_reasons:
            pieces.append("；".join(match_reasons[:2]))
        if baseline.school_level:
            pieces.append(f"院校层级：{baseline.school_level}")
        return "，".join(pieces) + "。"

    def _build_major_comment(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        baseline: GaokaoAdmissionBaseline,
        rank_gap: int,
        score_gap: int,
    ) -> str:
        major = baseline.major
        city = baseline.city
        comments: list[str] = []

        if any(word in major for word in ["计算机", "软件", "电子", "电气", "自动化"]):
            comments.append("这类专业就业口径普遍更宽，普通家庭更适合优先看专业实力和城市机会。")
        elif any(word in major for word in ["法学", "会计", "师范", "汉语言", "新闻"]):
            comments.append("这类专业更看重个人路径设计，读研、考编、考公和实习资源会直接影响后续上限。")
        elif any(word in major for word in ["金融", "财经"]):
            comments.append("金融财经不只看专业名，城市平台、学校层级和实习渠道往往比课表更重要。")
        elif any(word in major for word in ["医学", "护理", "临床", "口腔"]):
            comments.append("医学线培养周期更长，更适合目标明确、能接受长期投入的同学。")
        else:
            comments.append("这个专业不能只看名字，最好继续核对课程设置、读研比例和毕业去向。")

        city_hits = [token for token in self._tokenize(payload.preferred_cities) if token.lower() in city.lower()]
        if city_hits:
            comments.append(f"{city}和你的城市偏好直接重合，后续要重点看这座城市能不能给到实习、读研和就业机会。")
        elif payload.preferred_cities:
            comments.append(f"{city}不在你明确偏好的城市里，除非专业优势足够明显，否则不要只因为学校名字硬上。")
        else:
            comments.append(f"{city}的城市资源和实习承接，需要和学校层级一起看，别只看一张分数线。")

        if rank_gap >= 12000 and score_gap <= -20:
            comments.append("从位次和分数上看更偏保底，可以当成兜底选择，但也别把所有名额都放在过于轻松的学校上。")
        elif rank_gap < -9000 or score_gap > 25:
            comments.append("从位次上看更偏冲刺，如果特别想去，要接受专业调剂或结果波动。")
        else:
            comments.append("从位次上看属于可认真研究的一档，重点比较专业实力、城市和学费。")

        return "".join(comments[:3])

    def _build_direction_cards(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
    ) -> list[dict[str, str]]:
        line_map = {item.line_type: item.score for item in control_lines}
        cards = [
            {
                "title": "当前定位",
                "content": (
                    f"你在吉林{TRACK_LABELS[track]}中约位于第{rank}名，当前分数{score}分，"
                    f"比本科线高{score - line_map.get('undergraduate', 0)}分。"
                ),
            }
        ]

        if track == "physics":
            cards.append(
                {
                    "title": "方向优先级",
                    "content": (
                        "物理类不要先沉迷学校名头，先看专业出口。普通家庭更适合优先研究计算机、电气、自动化、电子信息、"
                        "机械、临床医学这类就业链路更清楚的方向。"
                    ),
                }
            )
        else:
            cards.append(
                {
                    "title": "方向优先级",
                    "content": (
                        "历史类更要防止‘名字好听但出口模糊’。优先看师范、法学、会计、汉语言、新闻传播这些后续路径更清晰的方向，"
                        "再决定学校层级。"
                    ),
                }
            )

        if payload.preferred_cities:
            cards.append(
                {
                    "title": "城市判断",
                    "content": f"你偏好“{payload.preferred_cities}”，这意味着城市资源、实习机会和未来就业半径也应该纳入一票否决项。",
                }
            )
        else:
            cards.append(
                {
                    "title": "城市判断",
                    "content": "如果暂时没有城市偏好，建议优先把长春、沈阳、大连、天津、北京、杭州这类资源更密集的城市放在前面研究。",
                }
            )

        if payload.family_budget:
            cards.append(
                {
                    "title": "预算约束",
                    "content": self._build_budget_card_content(payload.family_budget),
                }
            )
        return cards

    def _build_advisor_takeaways(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        anchor = self._pick_anchor_recommendation(recommendations)
        takeaways = [
            f"先说结论：你这档位更适合“先定方向，再做冲稳保”，而不是为了学校名头把专业完全让出去。",
            f"你现在约第{rank}名，已经具备认真挑专业的空间，别把志愿填报做成单纯的分数换学校游戏。",
        ]
        if anchor and self._has_strong_direction_match(anchor):
            takeaways.append(f"目前推荐里，像“{anchor['school']}”这类院校可以重点研究，但一定要把专业、城市、学费、保研或考公路径一起看。")
        else:
            takeaways.append("当前公开数据样本里，和你方向高度贴合的院校还不算多，所以这版名单更适合先定梯度和边界，不适合直接当成最终专业确认单。")
        if payload.preferred_majors:
            takeaways.append(f"你已经给出了意向专业“{payload.preferred_majors}”，这很好，后面所有筛选都要围绕这个核心，不要轻易被校名带跑。")
        if track == "history":
            takeaways.append("历史类最怕的是专业名字体面、就业出口模糊，所以每个选择都要问一句：毕业以后到底往哪里走。")
        else:
            takeaways.append("物理类最大的优势是专业出口更宽，真正要做的是把这种优势换成将来更稳定的城市和岗位。")
        return takeaways[:5]

    def _build_school_choice_logic(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        logic = [
            "第一原则不是盲冲名校，而是先判断这个分数段有没有必要为了学校层级牺牲专业方向。",
            "第二原则是城市资源和行业机会不能忽略，同层次学校里，城市更强的一方往往会在实习和就业上更占便宜。",
            "第三原则是普通家庭更要考虑性价比，学费、读研成本、考公考编路径都是真问题，不是小问题。",
        ]
        if recommendations:
            logic.append(
                f"你当前推荐池里已经同时给了冲、稳、保三档，正确用法不是平均分配，而是围绕1到2条主方向去排阵型。"
            )
            logic.append("如果你发现主推荐池里学校还不够多，不要急着怀疑自己没学校可报，先去看后面的方向扩展池，它是专门用来补专业路线的。")
        if payload.preferred_cities:
            logic.append(f"你写了意向城市“{payload.preferred_cities}”，所以学校选择时要把城市作为专业后的第二筛选条件。")
        return logic[:5]

    def _build_major_observations(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        observations: list[str] = []
        preferred_majors = self._tokenize(payload.preferred_majors)

        if preferred_majors:
            observations.append(
                f"你当前最应该做的是把“{'、'.join(preferred_majors[:3])}”拆成具体专业方向，而不是停留在大类名称。"
            )
            if not any(self._has_strong_direction_match(item) for item in recommendations):
                observations.append(
                    f"当前公开分数样本里，与“{'、'.join(preferred_majors[:2])}”高度贴合的院校还不算厚，所以你要把主推荐池和后面的方向扩展池结合着看。"
                )

        if track == "physics":
            observations.extend(
                [
                    "工科和信息类看上去都很像，但课程难度、就业行业、读研价值差异很大，别把“计算机、电子、电气、自动化”当成一个东西。",
                    "如果未来倾向稳定就业，优先研究电气、自动化、医学、师范等路径更明确的专业；如果更想冲上限，再看计算机和电子信息。",
                ]
            )
        else:
            observations.extend(
                [
                    "历史类专业尤其要看毕业后去向，是否适合考编、考公、读研，比专业名字更重要。",
                    "法学、会计、师范、汉语言这几条线，各自路径完全不同，建议后续按“就业/考编/升学”三个方向分开研究。",
                ]
            )

        if any("中外合作" in (item.get("school_level") or "") for item in recommendations):
            observations.append("推荐里如果出现中外合作项目，一定要把总学费和家庭承受能力单独核算，不要只看录取分低。")

        return observations[:5]

    def _build_major_breakdown(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
    ) -> list[dict[str, str]]:
        direction_keys = self._detect_direction_keys(payload, track)
        cards: list[dict[str, str]] = []

        if track == "physics" and "electronic_info" in direction_keys:
            cards.extend(
                [
                    {
                        "title": "硬件通信线",
                        "content": (
                            "这条路更接近电子信息工程、通信工程、电子科学与技术。课程会碰到模电数电、信号系统、通信原理，"
                            "适合愿意学底层硬件、后续能接受读研或做研发测试的学生。"
                        ),
                    },
                    {
                        "title": "电气自动化线",
                        "content": (
                            "这条路更接近电气工程及其自动化、自动化、测控。它通常没有计算机那样热闹，但就业口径更稳，"
                            "对普通家庭尤其友好，考公、进国企、进工程单位都更容易落地。"
                        ),
                    },
                    {
                        "title": "计算机数据线",
                        "content": (
                            "这条路更接近计算机科学与技术、软件工程、数据科学与大数据技术。上限高、城市资源敏感、竞争也卷，"
                            "更适合愿意持续学习、愿意为城市平台和读研机会投入的人。"
                        ),
                    },
                    {
                        "title": "数智转轨线",
                        "content": (
                            f"像信息管理与信息系统、数据科学这种专业，对你这种第{rank}名、{score}分的吉林物理类考生很有价值："
                            "它不一定最硬核，但更容易兼顾长春、本地落地、后期考研和数字化岗位。"
                        ),
                    },
                ]
            )
        elif track == "physics":
            cards.append(
                {
                    "title": "工科分流提醒",
                    "content": "物理类看起来都叫工科，但机械、电气、自动化、电子、计算机是五条不同路径，后面选学校之前一定先把这件事问清楚。",
                }
            )
        else:
            cards.append(
                {
                    "title": "文科分流提醒",
                    "content": "历史类更要先分清楚考编型、考公型、财经型和内容传播型，不要把名字体面的专业混在一起看。",
                }
            )
        return cards

    def _build_signature_advice(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        notes = (payload.notes or "").replace(" ", "")
        advice: list[str] = []
        direction_keys = self._detect_direction_keys(payload, track)

        if track == "physics" and "electronic_info" in direction_keys:
            advice.append("别把“电子信息”四个字当成一个专业，它至少分硬件通信、电气自动化、计算机数据、数智转轨四条路。")
            advice.append(
                f"你现在吉林物理类约第{rank}名，最怕的是为了学校名头硬冲一圈，最后既没保住电子信息相关方向，也没保住城市资源。"
            )
            if payload.preferred_cities:
                advice.append(
                    f"你既然明确提到了“{payload.preferred_cities}”，那就别只问‘能上什么学校’，还要问‘这个城市能不能给我实习、考研和第一份工作’。"
                )
            if "考研" in notes:
                advice.append("既然后期考研已经写进计划，本科阶段就更应该优先选课程底子更硬、工科氛围更强、城市实习更方便的学校。")
            if "调剂" in notes:
                advice.append("你能接受调剂是加分项，但接受调剂不等于放弃方向，电子信息大类里也要尽量守住电气、自动化、电子、计算机这些硬出口。")
        else:
            advice.append("真正好的志愿报告，不是把学校列一堆，而是把你以后往哪条路走先讲清楚。")

        if recommendations:
            advice.append("这次我把学校池拆成了‘主推荐池 + 方向扩展池’，前者解决能不能报，后者解决值不值得继续深挖。")
        return advice[:5]

    def _build_school_pool_note(self, payload: GaokaoPlanRequest, extended_pool: list[dict[str, Any]]) -> str | None:
        if not extended_pool:
            return None
        preferred_majors = payload.preferred_majors or "当前方向"
        return (
            f"这组扩展池不是让你全部填进去，而是专门帮你把“{preferred_majors}”拆成可报池、上限池和补位池。"
            "主推荐解决梯度，扩展池解决方向。"
        )

    def _build_extended_pool(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        direction_keys = self._detect_direction_keys(payload, track)
        if not direction_keys:
            return []

        existing_keys = {(item.get("school"), item.get("major")) for item in recommendations}
        rows = [
            item
            for item in load_jilin_direction_pool()
            if item.get("track") == track
            and set(item.get("direction_keys", [])).intersection(direction_keys)
        ]

        results: list[dict[str, Any]] = []
        for row in rows:
            key = (row.get("school"), row.get("major"))
            if key in existing_keys:
                continue

            reference_score = row.get("reference_score")
            reference_rank = row.get("reference_rank")
            if reference_rank is None and isinstance(reference_score, int):
                reference_rank = self._lookup_rank(track, reference_score)

            score_gap = None
            rank_gap = None
            if isinstance(reference_score, int):
                score_gap = reference_score - score
            if isinstance(reference_rank, int):
                rank_gap = reference_rank - rank

            group = self._extended_group_for(score_gap=score_gap, rank_gap=rank_gap, evidence_type=str(row.get("evidence_type") or "plan"))
            if group is None:
                continue

            fit_score, decision_tags = self._score_extended_pool_item(payload, row)
            results.append(
                {
                    "school": row.get("school"),
                    "major": row.get("major"),
                    "city": row.get("city"),
                    "school_level": row.get("school_level"),
                    "group": group,
                    "fit_label": self._extended_fit_label(group, score_gap, rank_gap),
                    "reason": self._build_extended_reason(payload, row, score_gap, rank_gap),
                    "decision_tags": decision_tags,
                    "evidence_type": row.get("evidence_type"),
                    "evidence_label": self._extended_evidence_label(str(row.get("evidence_type") or "plan")),
                    "reference_year": row.get("reference_year"),
                    "reference_score": reference_score,
                    "reference_rank": reference_rank,
                    "source_name": row.get("source_name"),
                    "source_url": row.get("source_url"),
                    "_fit_score": fit_score,
                    "_score_gap": score_gap if score_gap is not None else 999,
                    "_rank_gap": abs(rank_gap) if rank_gap is not None else 999999,
                }
            )

        results = sorted(
            results,
            key=lambda item: (
                EXTENDED_GROUP_PRIORITY.get(item["group"], 9),
                -item["_fit_score"],
                item["_rank_gap"],
                item["_score_gap"],
            ),
        )[:12]

        for item in results:
            item.pop("_fit_score", None)
            item.pop("_score_gap", None)
            item.pop("_rank_gap", None)
        return results

    def _detect_direction_keys(self, payload: GaokaoPlanRequest, track: str) -> list[str]:
        text = " ".join(
            part
            for part in [
                payload.preferred_majors or "",
                payload.career_preferences or "",
                payload.notes or "",
            ]
            if part
        )
        keys: list[str] = []
        if track == "physics":
            if any(token in text for token in DIRECTION_ALIAS_MAP["electronic_info"]):
                keys.append("electronic_info")
        return keys

    def _score_extended_pool_item(
        self,
        payload: GaokaoPlanRequest,
        row: dict[str, Any],
    ) -> tuple[int, list[str]]:
        haystack = " ".join(
            [
                str(row.get("school") or ""),
                str(row.get("major") or ""),
                str(row.get("city") or ""),
                str(row.get("school_level") or ""),
                str(row.get("direction_tags") or ""),
                str(row.get("note") or ""),
            ]
        ).lower()
        score = 40
        tags: list[str] = []

        major_hits = [token for token in self._tokenize(payload.preferred_majors) if token.lower() in haystack]
        if major_hits:
            score += 18
            tags.append("专业贴合")

        city_hits = [token for token in self._tokenize(payload.preferred_cities) if token.lower() in str(row.get("city") or "").lower()]
        if city_hits:
            score += 12
            tags.append("城市贴合")

        career_pref = payload.career_preferences or ""
        if any(word in career_pref for word in ["工程", "技术", "就业"]) and any(word in haystack for word in ["电气", "自动化", "工程", "就业"]):
            score += 10
            tags.append("就业导向")
        if any(word in career_pref for word in ["读研", "深造"]) and any(word in haystack for word in ["读研", "数据", "电子", "计算机"]):
            score += 8
            tags.append("读研友好")
        if row.get("evidence_type") == "public_baseline":
            score += 10
            tags.append("公开分数")
        elif row.get("evidence_type") == "plan":
            tags.append("官方计划")
        else:
            tags.append("方向样本")
        return score, list(dict.fromkeys(tags))[:4]

    def _extended_group_for(
        self,
        score_gap: int | None,
        rank_gap: int | None,
        evidence_type: str,
    ) -> str | None:
        if score_gap is not None:
            if score_gap > 70 or (rank_gap is not None and rank_gap < -26000):
                return None
            if score_gap <= 28 and (rank_gap is None or rank_gap > -10000):
                return "数据锚定补强池"
            if score_gap <= 55:
                return "上限参考池"
            return None
        if evidence_type == "plan":
            return "方向扩展关注池"
        return "上限参考池"

    def _extended_fit_label(
        self,
        group: str,
        score_gap: int | None,
        rank_gap: int | None,
    ) -> str:
        if group == "数据锚定补强池":
            if score_gap is not None and score_gap <= -20:
                return "可做保底增强"
            if score_gap is not None and score_gap <= 10:
                return "可重点研究"
            return "可做冲稳补强"
        if group == "方向扩展关注池":
            return "需核线后纳入"
        if rank_gap is not None and rank_gap < -12000:
            return "明显上限样本"
        return "方向上限参考"

    def _extended_evidence_label(self, evidence_type: str) -> str:
        labels = {
            "public_baseline": "2025公开录取分数",
            "public_query": "2025公开查询线索",
            "plan": "2025吉林招生计划",
            "program_profile": "官方专业介绍",
            "school_summary": "校方年度综述",
        }
        return labels.get(evidence_type, "公开信息")

    def _build_extended_reason(
        self,
        payload: GaokaoPlanRequest,
        row: dict[str, Any],
        score_gap: int | None,
        rank_gap: int | None,
    ) -> str:
        pieces: list[str] = []
        if isinstance(row.get("reference_score"), int):
            pieces.append(f"{row.get('reference_year')}年吉林公开最低分约{row.get('reference_score')}分")
        else:
            pieces.append(f"{row.get('reference_year')}年吉林公开资料里能确认该专业有招生线索")
        if isinstance(row.get("reference_rank"), int):
            pieces.append(f"参考位次约{row.get('reference_rank')}名")
        if score_gap is not None:
            pieces.append(f"与你当前分数大约相差{score_gap:+d}分")
        if rank_gap is not None:
            pieces.append(f"与你当前位次大约相差{rank_gap:+d}名")
        if payload.preferred_cities and any(token in str(row.get("city") or "") for token in self._tokenize(payload.preferred_cities)):
            pieces.append("城市与你的明确偏好重合")
        if row.get("note"):
            pieces.append(str(row["note"]))
        return "，".join(pieces[:4]) + "。"

    def _build_strategy(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
    ) -> list[str]:
        line_map = {item.line_type: item.score for item in control_lines}
        tips = [
            f"先用吉林{TRACK_LABELS[track]}一分一段把自己定位到约第{rank}名，再围绕这个位次做院校筛选，不要只盯分数。",
            f"你当前较特控线{'高' if score >= line_map.get('special', 0) else '低'}{abs(score - line_map.get('special', 0))}分，说明你有一定选择空间，但还没到可以随便任性的程度。",
            "志愿结构建议做成“2个冲方向、4个稳方向、4个保方向”的思路，同一方向尽量多留几个可替换方案。",
            "主推荐池负责正式填报梯度，方向扩展池负责第二轮缩圈和补专业路线，别把这两件事混成一件事。",
        ]
        if payload.preferred_majors:
            tips.append(f"意向专业“{payload.preferred_majors}”要优先看课程、去向和所在城市，不要只被学校名头带节奏。")
        return tips[:5]

    def _build_risk_notes(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        notes = [
            "这版结果已经能做方向判断和冲稳保初筛，但它仍然是公开数据版，不等同于完整志愿填报系统。",
            "公开录取最低分只代表去年的门槛，不代表今年一定能录；真正填报时还要看招生计划、专业组、服从调剂和院校冷热变化。",
            "如果你更看重将来稳定就业，就别把所有机会都押在冲档学校上，至少留出两档真正能兜底的专业。",
        ]
        if self._is_budget_sensitive(payload.family_budget):
            notes.append("家庭预算偏谨慎时，要特别注意民办和中外合作项目的总成本，不能只看入学那一年。")
        elif payload.family_budget:
            notes.append("预算不是核心约束时，也别因为‘无所谓’就忽略学费和培养地点，尤其是中外合作项目要单独算总账。")
        if any((item.get("bucket") == "chong" and item.get("risk_level") == "high") for item in recommendations):
            notes.append("本次冲档池里有部分学校更偏抬上限角色，如果非常执着，就要提前接受录取波动和专业调剂。")
        if len(recommendations) < 8:
            notes.append("当前吉林公开数据种子还不是完整院校库，所以本次更强调方向判断和高相关院校，不建议把院校数量少理解成可报学校就这些。")
        return notes[:5]

    def _build_execution_checklist(
        self,
        payload: GaokaoPlanRequest,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        checklist = [
            "把本页推荐院校按“最想去 / 可以接受 / 只做保底”重新手动分组，不要直接照抄。",
            "逐个核对专业的学费、培养地点、是否中外合作、是否需要读研、近年就业去向。",
            "对最想去的3到5个专业，额外查一遍课程设置和毕业去向，确认自己不是只喜欢名字。",
        ]
        if payload.preferred_cities:
            checklist.append(f"重点复核意向城市“{payload.preferred_cities}”里的院校，看未来实习和落户是否匹配你的期待。")
        if recommendations:
            checklist.append("正式填报前，再把冲、稳、保三档按顺序拉开梯度，不要让同一档位全部挤在一起。")
            checklist.append("把方向扩展池里真正想深挖的学校单独拉出来，二次去查招生计划、专业组和培养地点。")
        return checklist[:5]

    def _build_summary(
        self,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
        recommendations: list[dict[str, Any]],
    ) -> str:
        line_map = {item.line_type: item.score for item in control_lines}
        focus = self._recommendation_focus(recommendations)
        return (
            f"按吉林省{YEAR}年公开数据，你当前属于{TRACK_LABELS[track]}约第{rank}名，"
            f"分数为{score}分，较本科线高{score - line_map.get('undergraduate', 0)}分。"
            f"这不是一个适合盲冲名校的档位，更适合采用“先顾方向、再做冲稳保”的填报策略："
            f"先把专业出口、城市资源、家庭预算想明白，再去决定学校层级，本次推荐会以“{focus}”为主骨架。"
        )

    def _pick_anchor_recommendation(self, recommendations: list[dict[str, Any]]) -> dict[str, Any] | None:
        for bucket in ("wen", "bao", "chong"):
            for item in recommendations:
                if item.get("bucket") == bucket and self._has_strong_direction_match(item):
                    return item
        for bucket in ("wen", "bao", "chong"):
            for item in recommendations:
                if item.get("bucket") == bucket:
                    return item
        return recommendations[0] if recommendations else None

    def _recommendation_focus(self, recommendations: list[dict[str, Any]]) -> str:
        buckets = {item.get("bucket") for item in recommendations}
        if "wen" in buckets:
            return "稳档和保档"
        if "bao" in buckets:
            return "保档"
        if "chong" in buckets:
            return "冲档"
        return "稳档"

    def _is_budget_sensitive(self, family_budget: str | None) -> bool:
        if not family_budget:
            return False
        normalized = family_budget.replace(" ", "")
        if any(word in normalized for word in ["无所谓", "都可以", "不敏感", "不是问题", "学费不是主要问题"]):
            return False
        return any(word in normalized for word in ["公办", "低", "有限", "一般", "控制", "谨慎", "普通"])

    def _build_budget_card_content(self, family_budget: str) -> str:
        if self._is_budget_sensitive(family_budget):
            return f"家庭预算偏好为“{family_budget}”，所以推荐会主动压低高学费、中外合作和民办项目的优先级。"
        return f"家庭预算偏好为“{family_budget}”，说明学费不是最强约束，但中外合作、异地培养和读研成本仍然要单独核算。"

    def _has_strong_direction_match(self, recommendation: dict[str, Any]) -> bool:
        tags = set(recommendation.get("decision_tags") or [])
        return bool(tags.intersection({"专业贴合", "职业导向"}))
