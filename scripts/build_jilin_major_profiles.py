from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = ROOT / "资料库" / "00、志愿填报必备资料"
OUTPUT_DIR = ROOT / "data" / "gaokao" / "normalized" / "jilin_library"


TARGET_KEYWORDS = {
    "major_detail": ["院校专业详情(本科)"],
    "major_openings": ["全国高等院校开设专业汇总"],
    "major_catalog": ["普通高等学校本科专业目录（2023年完整版）"],
    "major_career": ["专业-职业", "2024年版"],
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").strip()
    if text.lower() == "nan":
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_list(value: Any) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    for token in ["；", ";", "、", "/", "|", "，", ","]:
        text = text.replace(token, "|")
    return [item.strip() for item in text.split("|") if item.strip()]


def discover_files() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in LIBRARY_ROOT.rglob("*.xls*"):
        raw = str(path)
        for key, keywords in TARGET_KEYWORDS.items():
            if key in found:
                continue
            if all(keyword in raw for keyword in keywords):
                found[key] = path
    return found


def find_header_row(df: pd.DataFrame, required_labels: list[str]) -> int:
    preview = df.head(20).fillna("")
    for idx, row in preview.iterrows():
        joined = " ".join(normalize_text(value) for value in row.tolist())
        if all(label in joined for label in required_labels):
            return int(idx)
    return 0


def pick_column(columns: list[Any], preferred_labels: list[str], fuzzy_labels: list[str] | None = None) -> Any | None:
    fuzzy_labels = fuzzy_labels or []
    for label in preferred_labels:
        for col in columns:
            if normalize_text(col) == label:
                return col
    for label in preferred_labels:
        for col in columns:
            if label in normalize_text(col):
                return col
    for label in fuzzy_labels:
        for col in columns:
            if label in normalize_text(col):
                return col
    return None


def parse_major_detail(path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    rows: dict[str, dict[str, Any]] = {}
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get("专业"))
        if not major:
            continue
        rows[major] = {
            "major_name": major,
            "discipline": normalize_text(raw.get("学科门类")),
            "major_category": normalize_text(raw.get("一级学科")),
            "duration": normalize_text(raw.get("年限")),
            "degree": normalize_text(raw.get("授予学位")),
            "science_ratio": normalize_text(raw.get("文理比例")),
            "training_goal": normalize_text(raw.get("培养目标")),
            "overview": normalize_text(raw.get("专业解读")),
            "employment_rate": normalize_text(raw.get("就业率")),
            "salary_after_5y": normalize_text(raw.get("毕业五年月薪")),
            "salary_rank": normalize_text(raw.get("专业薪酬排名")),
            "top_jobs": normalize_list(raw.get("毕业去向最多岗位")),
        }
    return rows


def parse_major_openings(path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    openings: dict[str, dict[str, Any]] = defaultdict(lambda: {"schools": set(), "categories": set(), "disciplines": set()})
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get("专业名称"))
        school = normalize_text(raw.get("学校"))
        if not major:
            continue
        if school:
            openings[major]["schools"].add(school)
        category = normalize_text(raw.get("专业类别"))
        discipline = normalize_text(raw.get("学科门类"))
        if category:
            openings[major]["categories"].add(category)
        if discipline:
            openings[major]["disciplines"].add(discipline)
    return openings


def parse_major_catalog(path: Path) -> dict[str, dict[str, Any]]:
    raw_df = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = find_header_row(raw_df, ["专业名称", "专业代码"])
    df = pd.read_excel(path, sheet_name=0, header=header_row, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]

    major_col = pick_column(list(df.columns), ["专业名称"])
    code_col = pick_column(list(df.columns), ["专业代码"])
    category_col = pick_column(list(df.columns), ["专业类"])
    level_col = pick_column(list(df.columns), ["学位授予门类"], ["层次"])

    rows: dict[str, dict[str, Any]] = {}
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get(major_col))
        if not major:
            continue
        rows[major] = {
            "catalog_major_code": normalize_text(raw.get(code_col)),
            "catalog_category": normalize_text(raw.get(category_col)),
            "catalog_level": normalize_text(raw.get(level_col)),
        }
    return rows


def parse_major_career(path: Path) -> dict[str, dict[str, Any]]:
    raw_df = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = find_header_row(raw_df, ["职业名称", "专业名称"])
    df = pd.read_excel(path, sheet_name=0, header=header_row, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]

    columns = list(df.columns)
    major_col = pick_column(columns, ["专业名称"], ["专业"])
    career_col = pick_column(columns, ["职业名称"], ["职业"])
    level_col = pick_column(columns, ["院校类型"], ["层次"])

    rows: dict[str, dict[str, Any]] = defaultdict(lambda: {"career_paths": set()})
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        level = normalize_text(raw.get(level_col))
        if level and "本科" not in level:
            continue
        major = normalize_text(raw.get(major_col))
        career = normalize_text(raw.get(career_col))
        if not major or not career:
            continue
        rows[major]["career_paths"].add(career)
    return rows


def infer_similar_majors(major_name: str, major_index: dict[str, dict[str, Any]]) -> list[str]:
    current = major_index.get(major_name) or {}
    category = current.get("major_category") or current.get("catalog_category") or ""
    discipline = current.get("discipline") or ""
    related: list[tuple[int, str]] = []
    tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z]+", major_name))
    for name, payload in major_index.items():
        if name == major_name:
            continue
        score = 0
        if category and category == (payload.get("major_category") or payload.get("catalog_category") or ""):
            score += 4
        if discipline and discipline == payload.get("discipline"):
            score += 2
        name_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z]+", name))
        overlap = len(tokens.intersection(name_tokens))
        score += min(overlap, 3)
        if score > 0:
            related.append((score, name))
    related.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in related[:8]]


def infer_strengths(payload: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    overview = payload.get("overview", "")
    jobs = payload.get("top_jobs") or []
    employment = payload.get("employment_rate", "")
    if payload.get("salary_after_5y"):
        strengths.append(f"五年月薪参考 {payload['salary_after_5y']}，市场化薪酬有一定支撑。")
    if employment:
        strengths.append(f"公开样本中的就业率参考 {employment}。")
    if jobs:
        strengths.append(f"高频岗位包括：{jobs[0]}。")
    if "交叉" in overview or "综合" in overview:
        strengths.append("专业交叉属性较强，后续转型空间相对更大。")
    return strengths[:4]


def infer_weaknesses(payload: dict[str, Any]) -> list[str]:
    weaknesses: list[str] = []
    overview = payload.get("overview", "")
    training_goal = payload.get("training_goal", "")
    if not payload.get("employment_rate"):
        weaknesses.append("缺少稳定的公开就业率样本，需要结合学校层次进一步判断。")
    if "基础" in training_goal or "理论" in training_goal:
        weaknesses.append("基础或理论训练偏重，如果只想快速就业，需要再看目标学校出口。")
    if "成材率偏低" in overview or "拒绝" in overview:
        weaknesses.append("对个人自驱和持续投入要求较高，不适合只想混文凭的路径。")
    if not weaknesses:
        weaknesses.append("同名专业在不同学校培养差异可能很大，不能只看专业名。")
    return weaknesses[:4]


def infer_postgraduate_paths(payload: dict[str, Any]) -> list[str]:
    category = payload.get("major_category") or ""
    major = payload.get("major_name") or ""
    paths: list[str] = []
    if any(token in category for token in ["电子", "通信", "电气", "自动化"]):
        paths.extend(["信息与通信工程", "电子科学与技术", "控制科学与工程"])
    if any(token in major for token in ["计算机", "数据", "人工智能", "软件"]):
        paths.extend(["计算机科学与技术", "软件工程", "人工智能"])
    if any(token in major for token in ["师范", "教育", "汉语言", "历史", "数学", "英语", "物理", "化学", "生物", "地理"]):
        paths.extend(["学科教育", "教育学", "相关学科专硕"])
    if any(token in major for token in ["中医", "中药", "针灸"]):
        paths.extend(["中医学", "中药学", "中西医结合"])
    if not paths:
        paths.append("建议结合目标学校往年推免、考研和跨考方向再细化。")
    seen: list[str] = []
    for item in paths:
        if item not in seen:
            seen.append(item)
    return seen[:5]


def merge_profiles(
    detail_rows: dict[str, dict[str, Any]],
    opening_rows: dict[str, dict[str, Any]],
    catalog_rows: dict[str, dict[str, Any]],
    career_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    all_names = sorted(set(detail_rows) | set(opening_rows) | set(catalog_rows) | set(career_rows))
    merged: dict[str, dict[str, Any]] = {}
    for major in all_names:
        detail = detail_rows.get(major, {})
        openings = opening_rows.get(major, {})
        catalog = catalog_rows.get(major, {})
        career = career_rows.get(major, {})
        merged[major] = {
            "major_name": major,
            "discipline": detail.get("discipline") or next(iter(openings.get("disciplines", [])), ""),
            "major_category": detail.get("major_category") or catalog.get("catalog_category") or next(iter(openings.get("categories", [])), ""),
            "duration": detail.get("duration") or "",
            "degree": detail.get("degree") or "",
            "science_ratio": detail.get("science_ratio") or "",
            "training_goal": detail.get("training_goal") or "",
            "overview": detail.get("overview") or "",
            "employment_rate": detail.get("employment_rate") or "",
            "salary_after_5y": detail.get("salary_after_5y") or "",
            "salary_rank": detail.get("salary_rank") or "",
            "top_jobs": detail.get("top_jobs") or [],
            "career_paths": sorted(career.get("career_paths", [])),
            "sample_schools": sorted(openings.get("schools") or set())[:20],
            "catalog_major_code": catalog.get("catalog_major_code") or "",
            "catalog_level": catalog.get("catalog_level") or "",
        }

    for major, payload in merged.items():
        payload["similar_majors"] = infer_similar_majors(major, merged)
        payload["strengths"] = infer_strengths(payload)
        payload["weaknesses"] = infer_weaknesses(payload)
        payload["postgraduate_paths"] = infer_postgraduate_paths(payload)
    return list(merged.values())


def main() -> None:
    files = discover_files()
    missing = sorted(set(TARGET_KEYWORDS) - set(files))
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    detail_rows = parse_major_detail(files["major_detail"])
    opening_rows = parse_major_openings(files["major_openings"])
    catalog_rows = parse_major_catalog(files["major_catalog"])
    career_rows = parse_major_career(files["major_career"])
    merged = merge_profiles(detail_rows, opening_rows, catalog_rows, career_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "jilin_major_profiles.json"
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"profiles": len(merged), "output": str(out_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
