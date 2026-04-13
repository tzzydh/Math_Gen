from __future__ import annotations

import re
from typing import Any

MAJOR_ALIAS_PREFERENCES = {
    "中医药": ["中医学", "中药学", "针灸推拿学", "中西医临床医学"],
    "电子信息": ["电子信息工程", "电子信息科学与技术", "通信工程", "电气工程及其自动化"],
    "计算机": ["计算机科学与技术", "软件工程", "数据科学与大数据技术", "人工智能"],
}


def build_major_profile(
    preferred_majors: str | None,
    recommendations: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    profile = match_major_profile(preferred_majors, profiles)
    if profile:
        return profile
    for item in recommendations:
        profile = match_major_profile(str(item.get("major") or ""), profiles)
        if profile:
            return profile
    return None


def match_major_profile(raw_major_text: str | None, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw_text = (raw_major_text or "").strip()
    if not raw_text or not profiles:
        return None

    alias_match = match_alias_profile(raw_text, profiles)
    if alias_match:
        return alias_match

    normalized_text = normalize_major_query(raw_text)
    best_row: dict[str, Any] | None = None
    best_score = -1

    for row in profiles:
        major_name = str(row.get("major_name") or "").strip()
        if not major_name:
            continue
        normalized_major = normalize_major_query(major_name)
        score = 0
        if normalized_text == normalized_major:
            score = 100
        elif normalized_text and normalized_text in normalized_major:
            score = 92
        elif normalized_major and normalized_major in normalized_text:
            score = 88
        else:
            query_tokens = set(major_tokens(normalized_text))
            major_tokens_set = set(major_tokens(normalized_major))
            overlap = len(query_tokens.intersection(major_tokens_set))
            score = overlap * 12
            if any(token and token in normalized_major for token in query_tokens):
                score += 8
            char_overlap = len(set(normalized_text).intersection(set(normalized_major)))
            score += min(char_overlap * 3, 15)

        if score > best_score:
            best_score = score
            best_row = row

    if best_score < 12 or not best_row:
        return None
    return normalize_major_profile(best_row)


def match_alias_profile(raw_major_text: str, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    for alias, preferred_names in MAJOR_ALIAS_PREFERENCES.items():
        if alias not in raw_major_text:
            continue
        for preferred_name in preferred_names:
            row = next((item for item in profiles if str(item.get("major_name") or "").strip() == preferred_name), None)
            if row:
                return normalize_major_profile(row)
    return None


def normalize_major_query(text: str) -> str:
    normalized = text.strip().replace("（", "(").replace("）", ")")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"\(.*?\)", "", normalized)
    normalized = normalized.replace("专业", "")
    return normalized


def major_tokens(text: str) -> list[str]:
    if not text:
        return []
    return [token for token in re.split(r"[、,，/()\-\s]+", text) if token]


def normalize_major_profile(row: dict[str, Any]) -> dict[str, Any]:
    def limit_list(value: Any, limit: int = 8) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in seen:
                seen.append(text)
        return seen[:limit]

    return {
        "major_name": str(row.get("major_name") or "").strip(),
        "discipline": str(row.get("discipline") or "").strip(),
        "major_category": str(row.get("major_category") or "").strip(),
        "duration": str(row.get("duration") or "").strip(),
        "degree": str(row.get("degree") or "").strip(),
        "science_ratio": str(row.get("science_ratio") or "").strip(),
        "training_goal": str(row.get("training_goal") or "").strip(),
        "overview": str(row.get("overview") or "").strip(),
        "employment_rate": str(row.get("employment_rate") or "").strip(),
        "salary_after_5y": str(row.get("salary_after_5y") or "").strip(),
        "salary_rank": str(row.get("salary_rank") or "").strip(),
        "top_jobs": limit_list(row.get("top_jobs"), 6),
        "career_paths": limit_list(row.get("career_paths"), 6),
        "sample_schools": limit_list(row.get("sample_schools"), 8),
        "catalog_major_code": str(row.get("catalog_major_code") or "").strip(),
        "catalog_level": str(row.get("catalog_level") or "").strip(),
        "similar_majors": limit_list(row.get("similar_majors"), 8),
        "strengths": limit_list(row.get("strengths"), 4),
        "weaknesses": limit_list(row.get("weaknesses"), 4),
        "postgraduate_paths": limit_list(row.get("postgraduate_paths"), 5),
    }


def build_major_breakdown(
    major_profile: dict[str, Any] | None,
    track: str,
    score: int,
    rank: int,
) -> list[dict[str, str]]:
    if major_profile:
        return [
            {
                "title": f"{major_profile['major_name']}专业定位",
                "content": join_sentences(
                    [
                        f"这类专业通常归在{major_profile.get('discipline') or '相关学科'}下的{major_profile.get('major_category') or '专业方向'}，学制{major_profile.get('duration') or '以学校公布为准'}，授予{major_profile.get('degree') or '对应学位'}。",
                        major_profile.get("overview") or major_profile.get("training_goal") or "",
                    ]
                ),
            },
            {
                "title": "课程、考研与就业",
                "content": join_sentences(
                    [
                        f"就业率参考{major_profile.get('employment_rate') or '公开样本不足'}，五年月薪参考{major_profile.get('salary_after_5y') or '公开样本不足'}。",
                        f"高频就业岗位包括：{'、'.join((major_profile.get('top_jobs') or [])[:4]) or '需结合目标学校细看'}。",
                        f"考研/深造方向常见为：{'、'.join((major_profile.get('postgraduate_paths') or [])[:4]) or '需结合目标学校细化'}。",
                    ]
                ),
            },
            {
                "title": "优势与短板",
                "content": join_sentences(
                    [
                        f"优势：{'；'.join((major_profile.get('strengths') or [])[:3]) or '需要结合学校平台判断'}。",
                        f"短板：{'；'.join((major_profile.get('weaknesses') or [])[:3]) or '需要结合课程和培养要求判断'}。",
                    ]
                ),
            },
            {
                "title": "相似专业与替代路线",
                "content": join_sentences(
                    [
                        f"相似专业可重点关注：{'、'.join((major_profile.get('similar_majors') or [])[:6]) or '暂无明确相似专业'}。",
                        "如果你当前分数对口学校不够理想，可以把这些相近专业一起纳入志愿池做比较。",
                        f"结合你现在约第{rank}名、{score}分的定位，建议把本专业和相似专业一起看，不要只盯住一个名字。",
                    ]
                ),
            },
        ]

    if track == "physics":
        return [
            {
                "title": "专业方向提醒",
                "content": "物理类不要只看学校名头，先把专业出口、课程难度、就业城市和读研路径想明白，再决定冲稳保的学校梯度。",
            }
        ]
    return [
        {
            "title": "专业方向提醒",
            "content": "历史类更要先想清楚未来是考编、考公、读研还是直接就业，不同路径对应的专业完全不是一回事。",
        }
    ]


def join_sentences(items: list[str]) -> str:
    parts = [str(item).strip() for item in items if str(item).strip()]
    return " ".join(parts)
