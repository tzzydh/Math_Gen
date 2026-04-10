from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.gaokao_admission_baseline import GaokaoAdmissionBaseline
from app.db.models.gaokao_control_line import GaokaoControlLine
from app.db.models.gaokao_score_rank import GaokaoScoreRank
from app.schemas.gaokao import GaokaoPlanRequest


YEAR = 2025
PROVINCE = "吉林省"

TRACK_LABELS = {
    "physics": "物理类",
    "history": "历史类",
}

BUCKET_LABELS = {
    "chong": "冲",
    "wen": "稳",
    "bao": "保",
}

LINE_LABELS = {
    "special": "特控线",
    "undergraduate": "本科线",
    "specialty": "专科线",
}


class GaokaoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_plan(self, payload: GaokaoPlanRequest) -> dict[str, Any]:
        province = self._normalize_province(payload.province)
        if province != PROVINCE:
            raise ValueError("当前高考数据版只支持吉林省")

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
            recommendations = self._build_fallback_recommendations(baselines, calculated_rank, payload)

        direction_cards = self._build_direction_cards(payload, track, score, calculated_rank, control_lines)
        direction_advice = [card["content"] for card in direction_cards]
        strategy = self._build_strategy(payload, track, score, calculated_rank, control_lines)
        risk_notes = self._build_risk_notes(payload, track, score, calculated_rank, control_lines)
        summary = self._build_summary(track, score, calculated_rank, control_lines, recommendations)

        return {
            "year": YEAR,
            "track": track,
            "calculated_rank": calculated_rank,
            "summary": summary,
            "direction_advice": direction_advice,
            "direction_cards": direction_cards,
            "strategy": strategy,
            "risk_notes": risk_notes,
            "control_lines": [
                {"line_type": line.line_type, "score": line.score}
                for line in control_lines
            ],
            "recommendations": recommendations,
            "raw_output": None,
        }

    def _normalize_province(self, value: str) -> str:
        normalized = re.sub(r"\s+", "", value or "")
        if normalized in {"吉林", "吉林省"}:
            return PROVINCE
        return value.strip()

    def _parse_positive_int(self, value: str | None, field_name: str) -> int:
        matched = re.findall(r"\d+", value or "")
        if not matched:
            raise ValueError(f"{field_name}格式不正确")
        return int(matched[0])

    def _infer_track(self, subject_combination: str) -> str:
        normalized = subject_combination.replace(" ", "")
        if "史" in normalized:
            return "history"
        if "物" in normalized:
            return "physics"
        raise ValueError("暂时只支持吉林省新高考物理类或历史类组合")

    def _resolve_rank(self, track: str, score: int, raw_rank: str | None) -> int:
        if raw_rank and raw_rank.strip():
            return self._parse_positive_int(raw_rank, "位次")

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
        for baseline in baselines:
            if baseline.min_rank is None:
                continue
            gap = rank - baseline.min_rank
            bucket = self._classify_bucket(gap)
            if bucket is None:
                continue

            match_score, match_reasons = self._score_direction_match(payload, track, baseline)
            fit_score = self._fit_score(bucket, gap, match_score)
            grouped[bucket].append(
                {
                    "school": baseline.school,
                    "major": baseline.major,
                    "city": baseline.city,
                    "school_level": baseline.school_level,
                    "bucket": bucket,
                    "fit_score": fit_score,
                    "risk_level": self._risk_level(bucket, gap),
                    "reason": self._build_reason(rank, baseline, bucket, match_reasons),
                    "data_year": baseline.data_year,
                    "min_score": baseline.min_score,
                    "min_rank": baseline.min_rank,
                    "source_name": baseline.source_name,
                }
            )

        results: list[dict[str, Any]] = []
        for bucket in ("chong", "wen", "bao"):
            bucket_items = sorted(
                grouped.get(bucket, []),
                key=lambda item: (-item["fit_score"], item["min_rank"] or math.inf),
            )[:3]
            results.extend(bucket_items)
        return results

    def _build_fallback_recommendations(
        self,
        baselines: list[GaokaoAdmissionBaseline],
        rank: int,
        payload: GaokaoPlanRequest,
    ) -> list[dict[str, Any]]:
        sorted_rows = sorted(
            [item for item in baselines if item.min_rank is not None],
            key=lambda item: abs((item.min_rank or rank) - rank),
        )[:4]
        results = []
        for item in sorted_rows:
            _, match_reasons = self._score_direction_match(payload, item.track, item)
            gap = rank - (item.min_rank or rank)
            bucket = self._classify_bucket(gap) or "chong"
            results.append(
                {
                    "school": item.school,
                    "major": item.major,
                    "city": item.city,
                    "school_level": item.school_level,
                    "bucket": bucket,
                    "fit_score": self._fit_score(bucket, gap, 0),
                    "risk_level": self._risk_level(bucket, gap),
                    "reason": self._build_reason(rank, item, bucket, match_reasons),
                    "data_year": item.data_year,
                    "min_score": item.min_score,
                    "min_rank": item.min_rank,
                    "source_name": item.source_name,
                }
            )
        return results

    def _classify_bucket(self, gap: int) -> str | None:
        if gap <= -7000:
            return "bao"
        if gap <= -1500:
            return "wen"
        if gap <= 2500:
            return "chong"
        return None

    def _score_direction_match(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        baseline: GaokaoAdmissionBaseline,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
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
            score += 18
            reasons.append(f"命中意向专业关键词：{'、'.join(major_hits[:3])}")

        city_hits = [token for token in city_pref if token.lower() in baseline.city.lower()]
        if city_hits:
            score += 12
            reasons.append(f"符合城市偏好：{'、'.join(city_hits[:2])}")

        career_map = {
            "稳定": ["师范", "医学", "会计", "法学", "教育"],
            "编制": ["师范", "教育", "医学", "会计"],
            "就业": ["计算机", "电气", "自动化", "会计", "护理"],
            "体制": ["师范", "法学", "会计", "医学"],
            "金融": ["金融", "会计", "财经"],
            "工科": ["工科", "计算机", "电子", "机械", "电气"],
        }
        for token in career_pref:
            for keyword, labels in career_map.items():
                if keyword in token and any(label in haystack for label in labels):
                    score += 10
                    reasons.append(f"和职业倾向“{token}”一致")
                    break

        if track == "physics" and not major_pref and any(word in haystack for word in ["计算机", "电气", "电子", "自动化", "机械"]):
            score += 8
            reasons.append("物理类下就业导向较稳")
        if track == "history" and not major_pref and any(word in haystack for word in ["法学", "会计", "师范", "汉语", "新闻"]):
            score += 8
            reasons.append("历史类下方向出口相对明确")

        if budget_pref and any(word in budget_pref for word in ["公办", "低", "一般", "有限"]):
            if baseline.school_level and ("中外合作" in baseline.school_level or "民办" in baseline.school_level):
                score -= 16
                reasons.append("家庭预算偏谨慎，不建议优先中外合作或民办")

        return score, reasons

    def _tokenize(self, raw_text: str | None) -> list[str]:
        if not raw_text:
            return []
        return [token for token in re.split(r"[、,，/\\\s]+", raw_text) if token]

    def _fit_score(self, bucket: str, gap: int, match_score: int) -> int:
        base = {"chong": 76, "wen": 84, "bao": 78}[bucket]
        closeness = max(0, 18 - min(abs(gap) // 400, 18))
        return max(50, min(99, base + closeness + match_score))

    def _risk_level(self, bucket: str, gap: int) -> str:
        if bucket == "bao":
            return "low"
        if bucket == "wen":
            return "medium"
        if gap > 1200:
            return "high"
        return "medium"

    def _build_reason(
        self,
        rank: int,
        baseline: GaokaoAdmissionBaseline,
        bucket: str,
        match_reasons: list[str],
    ) -> str:
        pieces = [
            f"{baseline.data_year}年吉林{TRACK_LABELS[baseline.track]}最低录取分为{baseline.min_score}分",
        ]
        if baseline.min_rank:
            pieces.append(f"最低位次约{baseline.min_rank}名，你当前位次约{rank}名")
        pieces.append(f"按当前公开数据属于“{BUCKET_LABELS[bucket]}”档")
        if match_reasons:
            pieces.append("；".join(match_reasons[:2]))
        if baseline.school_level:
            pieces.append(f"院校层级：{baseline.school_level}")
        return "，".join(pieces) + "。"

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
                "content": f"你在吉林{TRACK_LABELS[track]}中约位于第{rank}名，"
                f"当前分数{score}分，较本科线高{score - line_map.get('undergraduate', 0)}分。",
            }
        ]

        if track == "physics":
            cards.append(
                {
                    "title": "方向优先级",
                    "content": "物理类建议优先考虑计算机、电气、自动化、电子信息、机械、医学等出口更清晰的方向；若冲名校不稳，优先保专业而不是只保学校名气。",
                }
            )
        else:
            cards.append(
                {
                    "title": "方向优先级",
                    "content": "历史类建议优先考虑师范、法学、会计、汉语言、新闻传播等就业链路更明确的方向；避免只看学校名头而忽略专业出口。",
                }
            )

        if payload.preferred_cities:
            cards.append(
                {
                    "title": "城市建议",
                    "content": f"你偏好“{payload.preferred_cities}”，结果里会优先保留这些城市或就业半径更接近的院校。",
                }
            )
        else:
            cards.append(
                {
                    "title": "城市建议",
                    "content": "如果你暂时没有明确城市偏好，吉林考生建议优先考虑长春、沈阳、大连、天津、北京等资源密度更高、实习和就业承接更好的城市。",
                }
            )

        if payload.family_budget:
            cards.append(
                {
                    "title": "预算提醒",
                    "content": f"家庭预算偏好为“{payload.family_budget}”，我已在推荐中降低中外合作和高学费项目的优先级。",
                }
            )
        return cards

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
            f"先用吉林{TRACK_LABELS[track]}一分一段定位到约第{rank}名，再围绕这个位次做院校筛选，不要只盯分数。",
            f"你当前较特控线{'高' if score >= line_map.get('special', 0) else '低'}{abs(score - line_map.get('special', 0))}分，志愿组合要同时顾学校层级和专业出口。",
            "志愿结构优先保证“1-2个方向明确的稳项 + 2-3个保底专业”，冲项只负责抬上限，不负责兜底。",
        ]
        if payload.preferred_majors:
            tips.append(f"意向专业“{payload.preferred_majors}”要优先看专业实力和就业出口，避免为了学校名头放弃核心方向。")
        return tips[:4]

    def _build_risk_notes(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
    ) -> list[str]:
        notes = [
            "当前版本基于吉林省公开数据种子库，适合做第一轮筛选，不等同于完整志愿填报系统。",
            "公开录取最低分只代表去年的门槛，不代表今年一定能录取；实际填报还要结合招生计划、专业组和服从调剂。",
            "如果你更看重就业稳定性，建议优先公办、优先专业出口、优先城市资源，不建议把所有名额都押在冲档学校。",
        ]
        if payload.family_budget and any(word in payload.family_budget for word in ["公办", "低", "有限"]):
            notes.append("家庭预算偏谨慎时，要特别注意民办和中外合作项目的学费差异。")
        return notes[:4]

    def _build_summary(
        self,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
        recommendations: list[dict[str, Any]],
    ) -> str:
        line_map = {item.line_type: item.score for item in control_lines}
        top_bucket = BUCKET_LABELS.get(recommendations[0]["bucket"], "稳") if recommendations else "稳"
        return (
            f"按吉林省{YEAR}年公开数据，你当前属于{TRACK_LABELS[track]}约第{rank}名，"
            f"分数为{score}分，较本科线高{score - line_map.get('undergraduate', 0)}分。"
            f"当前更适合采用“先顾方向、再做冲稳保”的填报策略，优先把专业出口和城市资源放在前面，"
            f"推荐结果以“{top_bucket}”档起步。"
        )
