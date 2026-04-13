from __future__ import annotations

import re
from typing import Any


MAJOR_ALIAS_PREFERENCES = {
    "汉语言文学师范": ["汉语言文学", "汉语言文学（师范类）", "中国语言文学类"],
    "数学师范": ["数学与应用数学", "数学类", "信息与计算科学"],
    "英语师范": ["英语", "英语（师范类）", "商务英语"],
    "物理师范": ["物理学", "应用物理学"],
    "化学师范": ["化学", "应用化学"],
    "生物师范": ["生物科学", "生物技术"],
    "地理师范": ["地理科学", "人文地理与城乡规划"],
    "历史师范": ["历史学", "世界史"],
    "思想政治师范": ["思想政治教育", "政治学与行政学"],
    "中医药": ["中医学", "中药学", "针灸推拿学", "中西医临床医学", "康复治疗学"],
    "中医": ["中医学", "中西医临床医学", "针灸推拿学", "中药学"],
    "电子信息": ["电子信息工程", "电子科学与技术", "通信工程", "微电子科学与工程", "电气工程及其自动化"],
    "计算机": ["计算机科学与技术", "软件工程", "数据科学与大数据技术", "人工智能", "网络工程"],
    "师范": ["教育学", "小学教育", "学前教育", "汉语言文学", "数学与应用数学", "英语", "物理学", "化学", "生物科学", "地理科学", "思想政治教育"],
    "教育": ["教育学", "小学教育", "学前教育", "特殊教育", "教育技术学"],
    "广播": ["广播电视学", "广播电视编导", "播音与主持艺术", "网络与新媒体"],
}

THEME_KEYWORDS = {
    "teacher": ["师范", "教育", "学科教育", "小学教育", "学前教育", "特殊教育"],
    "medicine": ["中医", "中医药", "中药", "针灸", "康复", "临床"],
    "electronic": ["电子", "通信", "电气", "自动化", "微电子", "芯片", "信息"],
    "computer": ["计算机", "软件", "网络", "人工智能", "数据", "算法"],
    "media": ["广播", "播音", "编导", "影视", "新闻", "媒体"],
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
    query_theme = infer_query_theme(raw_text)
    best_row: dict[str, Any] | None = None
    best_score = -1

    for row in profiles:
        score = score_profile(normalized_text, query_theme, row)
        if score > best_score:
            best_score = score
            best_row = row

    if best_score < 18 or not best_row:
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


def infer_query_theme(text: str) -> str | None:
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return theme
    return None


def score_profile(normalized_text: str, query_theme: str | None, row: dict[str, Any]) -> int:
    major_name = str(row.get("major_name") or "").strip()
    if not major_name:
        return -1

    normalized_major = normalize_major_query(major_name)
    profile_blob = " ".join(
        [
            major_name,
            str(row.get("major_category") or ""),
            str(row.get("discipline") or ""),
            str(row.get("overview") or ""),
            " ".join(str(item) for item in row.get("similar_majors") or []),
        ]
    )
    normalized_blob = normalize_major_query(profile_blob)

    if query_theme and not theme_matches(query_theme, profile_blob):
        return 2

    score = 0
    if normalized_text == normalized_major:
        score += 100
    elif normalized_text and normalized_text in normalized_major:
        score += 92
    elif normalized_major and normalized_major in normalized_text:
        score += 86

    query_tokens = set(major_tokens(normalized_text))
    major_tokens_set = set(major_tokens(normalized_blob))
    overlap = len(query_tokens.intersection(major_tokens_set))
    score += overlap * 14

    for token in query_tokens:
        if token and token in normalized_blob:
            score += 5

    char_overlap = len(set(normalized_text).intersection(set(normalized_major)))
    score += min(char_overlap * 4, 20)

    if query_theme and theme_matches(query_theme, major_name):
        score += 24
    if query_theme and theme_matches(query_theme, str(row.get("major_category") or "")):
        score += 18

    if "师范" in normalized_text and "师范" not in normalized_major:
        if major_name not in {"教育学", "小学教育", "学前教育", "汉语言文学", "数学与应用数学", "英语", "物理学", "化学", "生物科学", "地理科学", "思想政治教育"}:
            score -= 18
    if "广播" in normalized_text and "广播" not in normalized_major:
        score -= 12
    if "中医" in normalized_text and "中医" not in normalized_blob:
        score -= 16

    return score


def theme_matches(theme: str, text: str) -> bool:
    return any(keyword in text for keyword in THEME_KEYWORDS.get(theme, []))


def normalize_major_query(text: str) -> str:
    normalized = text.strip().replace("（", "(").replace("）", ")")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"\(.*?\)", "", normalized)
    normalized = normalized.replace("专业", "")
    return normalized


def major_tokens(text: str) -> list[str]:
    if not text:
        return []
    return [token for token in re.split(r"[、，,；;()（）/\-\s]+", text) if token]


def normalize_major_profile(row: dict[str, Any]) -> dict[str, Any]:
    def limit_list(value: Any, limit: int = 8) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in seen and text.lower() != "nan":
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
        jobs = "、".join((major_profile.get("top_jobs") or [])[:4]) or "需要结合目标学校细看"
        postgraduate_paths = "、".join((major_profile.get("postgraduate_paths") or [])[:4]) or "建议结合目标学校推免和考研方向细化"
        similar_majors = "、".join((major_profile.get("similar_majors") or [])[:6]) or "暂无清晰相近专业"
        strengths = "；".join((major_profile.get("strengths") or [])[:3]) or "需要结合学校平台判断"
        weaknesses = "；".join((major_profile.get("weaknesses") or [])[:3]) or "需要结合课程强度和个人兴趣判断"
        return [
            {
                "title": f"{major_profile['major_name']}专业定位",
                "content": join_sentences(
                    [
                        f"这个专业通常归在 {major_profile.get('discipline') or '相关学科'} 下的 {major_profile.get('major_category') or '对应专业方向'}。",
                        f"学制一般为 {major_profile.get('duration') or '以学校公布为准'}，授予学位通常为 {major_profile.get('degree') or '对应学位'}。",
                        major_profile.get("overview") or major_profile.get("training_goal") or "",
                    ]
                ),
            },
            {
                "title": "课程、考研与就业",
                "content": join_sentences(
                    [
                        f"就业率参考 {major_profile.get('employment_rate') or '公开样本不足'}，五年月薪参考 {major_profile.get('salary_after_5y') or '公开样本不足'}。",
                        f"高频就业岗位包括：{jobs}。",
                        f"考研或深造常见方向：{postgraduate_paths}。",
                    ]
                ),
            },
            {
                "title": "优势与短板",
                "content": join_sentences(
                    [
                        f"优势：{strengths}。",
                        f"短板：{weaknesses}。",
                    ]
                ),
            },
            {
                "title": "相似专业与替代路线",
                "content": join_sentences(
                    [
                        f"相似专业可重点关注：{similar_majors}。",
                        f"结合你当前约第 {rank} 名、{score} 分的定位，建议把本专业和相近专业一起纳入比较，不要只盯住一个专业名。",
                    ]
                ),
            },
        ]

    if track == "physics":
        return [
            {
                "title": "专业方向提醒",
                "content": "物理类考生先看专业出口，再看学校名头。课程强度、就业行业、读研价值和城市资源都要一起判断。",
            }
        ]
    return [
        {
            "title": "专业方向提醒",
            "content": "历史类更要先想清楚未来是考编、考公、读研还是直接就业，不同路径对应的专业价值完全不同。",
        }
    ]


def join_sentences(items: list[str]) -> str:
    parts = [str(item).strip() for item in items if str(item).strip()]
    return " ".join(parts)
