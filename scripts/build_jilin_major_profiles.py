from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = ROOT / "\u8d44\u6599\u5e93" / "00\u3001\u5fd7\u613f\u586b\u62a5\u5fc5\u5907\u8d44\u6599"
OUTPUT_DIR = ROOT / "data" / "gaokao" / "normalized" / "jilin_library"


TARGET_FILES = {
    "major_detail": "2024\u5e74\u9662\u6821\u4e13\u4e1a\u8be6\u60c5(\u672c\u79d1).xlsx",
    "major_openings": "\u5168\u56fd\u9ad8\u7b49\u9662\u6821\u5f00\u8bbe\u4e13\u4e1a\u6c47\u603b.xlsx",
    "major_catalog": "\u7edd\u5bc6\u62a5\u8003-\u666e\u901a\u9ad8\u7b49\u5b66\u6821\u672c\u79d1\u4e13\u4e1a\u76ee\u5f55\uff082023\u5e74\u5b8c\u6574\u7248\uff09.xlsx",
    "major_career": "\u300a\u9662\u6821\u201c\u4e13\u4e1a-\u804c\u4e1a\u201d\u5bf9\u7167\u8868\uff082024\u5e74\u7248\uff09\u300b.xlsx",
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").strip()
    return re.sub(r"\s+", " ", text)


def normalize_list(value: Any, sep: str = "，") -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    for token in ["；", ";", "、", "/", "|"]:
        text = text.replace(token, sep)
    return [item.strip() for item in text.split(sep) if item.strip()]


def discover_files() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in LIBRARY_ROOT.rglob("*.xlsx"):
        for key, filename in TARGET_FILES.items():
            if path.name == filename:
                found[key] = path
    return found


def parse_major_detail(path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    rows: dict[str, dict[str, Any]] = {}
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get("\u4e13\u4e1a"))
        if not major:
            continue
        rows[major] = {
            "major_name": major,
            "discipline": normalize_text(raw.get("\u5b66\u79d1\u95e8\u7c7b")),
            "major_category": normalize_text(raw.get("\u4e00\u7ea7\u5b66\u79d1")),
            "duration": normalize_text(raw.get("\u5e74\u9650")),
            "degree": normalize_text(raw.get("\u6388\u4e88\u5b66\u4f4d")),
            "science_ratio": normalize_text(raw.get("\u6587\u7406\u6bd4\u4f8b")),
            "training_goal": normalize_text(raw.get("\u57f9\u517b\u76ee\u6807")),
            "overview": normalize_text(raw.get("\u4e13\u4e1a\u89e3\u8bfb")),
            "employment_rate": normalize_text(raw.get("\u5c31\u4e1a\u7387")),
            "salary_after_5y": normalize_text(raw.get("\u6bd5\u4e1a\u4e94\u5e74\u6708\u85aa")),
            "salary_rank": normalize_text(raw.get("\u4e13\u4e1a\u85aa\u916c\u6392\u540d")),
            "top_jobs": normalize_list(raw.get("\u6bd5\u4e1a\u53bb\u5411\u6700\u591a\u5c97\u4f4d")),
        }
    return rows


def find_header_row(df: pd.DataFrame, required_labels: list[str]) -> int:
    preview = df.head(20).fillna("")
    for idx, row in preview.iterrows():
        joined = " ".join(normalize_text(value) for value in row.tolist())
        if all(label in joined for label in required_labels):
            return int(idx)
    return 0


def parse_major_openings(path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    openings: dict[str, dict[str, Any]] = defaultdict(lambda: {"schools": set(), "categories": set(), "disciplines": set()})
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get("\u4e13\u4e1a\u540d\u79f0"))
        school = normalize_text(raw.get("\u5b66\u6821"))
        if not major:
            continue
        openings[major]["schools"].add(school)
        openings[major]["categories"].add(normalize_text(raw.get("\u4e13\u4e1a\u7c7b\u522b")))
        openings[major]["disciplines"].add(normalize_text(raw.get("\u5b66\u79d1\u95e8\u7c7b")))
    return openings


def parse_major_catalog(path: Path) -> dict[str, dict[str, Any]]:
    raw_df = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = find_header_row(raw_df, ["\u4e13\u4e1a\u540d\u79f0"])
    df = pd.read_excel(path, sheet_name=0, header=header_row, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    rows: dict[str, dict[str, Any]] = {}
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get("\u4e13\u4e1a\u540d\u79f0"))
        if not major:
            continue
        rows[major] = {
            "catalog_major_code": normalize_text(raw.get("\u4e13\u4e1a\u4ee3\u7801")),
            "catalog_category": normalize_text(raw.get("\u4e13\u4e1a\u7c7b")),
            "catalog_level": normalize_text(raw.get("\u5c42\u6b21")),
        }
    return rows


def parse_major_career(path: Path) -> dict[str, dict[str, Any]]:
    raw_df = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = find_header_row(raw_df, ["\u4e13\u4e1a", "\u804c\u4e1a"])
    df = pd.read_excel(path, sheet_name=0, header=header_row, dtype=object)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]

    major_col = next((col for col in df.columns if "\u4e13\u4e1a" in str(col)), None)
    career_col = next((col for col in df.columns if "\u804c\u4e1a" in str(col)), None)
    school_col = next((col for col in df.columns if "\u9662\u6821" in str(col)), None)

    rows: dict[str, dict[str, Any]] = defaultdict(lambda: {"career_paths": set(), "sample_schools": set()})
    for raw in df.astype(object).where(pd.notna(df), "").to_dict(orient="records"):
        major = normalize_text(raw.get(major_col))
        if not major:
            continue
        rows[major]["career_paths"].update(normalize_list(raw.get(career_col), sep="，"))
        if school_col:
            school = normalize_text(raw.get(school_col))
            if school:
                rows[major]["sample_schools"].add(school)
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
        score += min(overlap, 2)
        if score > 0:
            related.append((score, name))
    related.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in related[:8]]


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
            "sample_schools": sorted((openings.get("schools") or set()) | (career.get("sample_schools") or set()))[:20],
            "catalog_major_code": catalog.get("catalog_major_code") or "",
            "catalog_level": catalog.get("catalog_level") or "",
        }

    for major, payload in merged.items():
        payload["similar_majors"] = infer_similar_majors(major, merged)
        payload["strengths"] = infer_strengths(payload)
        payload["weaknesses"] = infer_weaknesses(payload)
        payload["postgraduate_paths"] = infer_postgraduate_paths(payload)
    return list(merged.values())


def infer_strengths(payload: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    overview = payload.get("overview", "")
    jobs = payload.get("top_jobs") or []
    employment = payload.get("employment_rate", "")
    if payload.get("salary_after_5y"):
        strengths.append(f"\u4e94\u5e74\u6708\u85aa\u53c2\u8003 {payload['salary_after_5y']}\uff0c\u6709\u4e00\u5b9a\u5e02\u573a\u8bbe\u5907\u503c")
    if employment:
        strengths.append(f"\u5c31\u4e1a\u7387\u53c2\u8003 {employment}\uff0c\u884c\u4e1a\u843d\u5730\u6027\u8f83\u5f3a")
    if jobs:
        strengths.append(f"\u5c31\u4e1a\u9762\u5411\u6bd4\u8f83\u6e05\u6670\uff0c\u9ad8\u9891\u5c97\u4f4d\u5305\u62ec\uff1a{jobs[0]}")
    if "\u4ea4\u53c9" in overview or "\u7efc\u5408" in overview:
        strengths.append("\u4ea4\u53c9\u5c5e\u6027\u8f83\u5f3a\uff0c\u540e\u7eed\u53ef\u4ee5\u5411\u591a\u4e2a\u65b9\u5411\u8f6c\u578b")
    return strengths[:4]


def infer_weaknesses(payload: dict[str, Any]) -> list[str]:
    weaknesses: list[str] = []
    overview = payload.get("overview", "")
    training_goal = payload.get("training_goal", "")
    if not payload.get("employment_rate"):
        weaknesses.append("\u7f3a\u5c11\u7a33\u5b9a\u7684\u516c\u5f00\u5c31\u4e1a\u7387\u6837\u672c\uff0c\u9700\u8981\u7ed3\u5408\u5b66\u6821\u5c42\u6b21\u5224\u65ad")
    if "\u57fa\u7840" in training_goal or "\u7406\u8bba" in training_goal:
        weaknesses.append("\u57fa\u7840\u6216\u7406\u8bba\u8bad\u7ec3\u6bd4\u8f83\u91cd\uff0c\u5982\u679c\u53ea\u60f3\u5feb\u901f\u5c31\u4e1a\u9700\u8981\u8fdb\u4e00\u6b65\u7b5b\u9009")
    if "\u6210\u6750\u7387\u504f\u4f4e" in overview or "\u62d2\u7edd" in overview:
        weaknesses.append("\u5bf9\u4e2a\u4eba\u81ea\u9a71\u548c\u6301\u7eed\u6295\u5165\u8981\u6c42\u9ad8\uff0c\u4e0d\u9002\u5408\u53ea\u60f3\u6df7\u6587\u51ed\u7684\u8def\u7ebf")
    if not weaknesses:
        weaknesses.append("\u4e13\u4e1a\u5185\u90e8\u65b9\u5411\u5dee\u5f02\u53ef\u80fd\u5f88\u5927\uff0c\u4e0d\u80fd\u53ea\u770b\u540d\u5b57\u5c31\u4e0b\u51b3\u5fc3")
    return weaknesses[:4]


def infer_postgraduate_paths(payload: dict[str, Any]) -> list[str]:
    category = payload.get("major_category") or ""
    major = payload.get("major_name") or ""
    paths: list[str] = []
    if any(token in category for token in ["\u7535\u5b50", "\u901a\u4fe1", "\u7535\u6c14", "\u81ea\u52a8\u5316"]):
        paths.extend(["\u4fe1\u606f\u4e0e\u901a\u4fe1\u5de5\u7a0b", "\u7535\u5b50\u79d1\u5b66\u4e0e\u6280\u672f", "\u63a7\u5236\u79d1\u5b66\u4e0e\u5de5\u7a0b"])
    if any(token in major for token in ["\u8ba1\u7b97\u673a", "\u6570\u636e", "\u4eba\u5de5\u667a\u80fd", "\u8f6f\u4ef6"]):
        paths.extend(["\u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f", "\u8f6f\u4ef6\u5de5\u7a0b", "\u4eba\u5de5\u667a\u80fd"])
    if any(token in major for token in ["\u5e08\u8303", "\u6559\u80b2", "\u6c49\u8bed", "\u5386\u53f2"]):
        paths.extend(["\u5b66\u79d1\u6559\u80b2", "\u6559\u80b2\u5b66", "\u76f8\u5173\u5b66\u79d1\u4e13\u7855"])
    if not paths:
        paths.append("\u5efa\u8bae\u7ed3\u5408\u76ee\u6807\u5b66\u6821\u5f80\u5e74\u63a8\u514d\u3001\u8003\u7814\u548c\u8de8\u8003\u65b9\u5411\u518d\u7ec6\u5316")
    seen = []
    for item in paths:
        if item not in seen:
            seen.append(item)
    return seen[:5]


def main() -> None:
    files = discover_files()
    missing = sorted(set(TARGET_FILES) - set(files))
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
