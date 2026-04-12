from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = ROOT / "\u8d44\u6599\u5e93"
OUTPUT_ROOT = ROOT / "data" / "gaokao"
RAW_OUTPUT = OUTPUT_ROOT / "raw" / "jilin_library"
NORMALIZED_OUTPUT = OUTPUT_ROOT / "normalized" / "jilin_library"
INDEX_OUTPUT = OUTPUT_ROOT / "indexes" / "jilin_library"
PROVINCE = "\u5409\u6797\u7701"


@dataclass(frozen=True)
class LocatedWorkbook:
    key: str
    path: Path


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).replace("\u3000", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_int(value: Any) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+", text.replace(",", ""))
    if not match:
        return None
    return int(match.group(0))


def normalize_year(value: Any) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    match = re.search(r"20\d{2}", text)
    if match:
        return int(match.group(0))
    match = re.search(r"\b(\d{2})\b", text)
    if match:
        return int(f"20{match.group(1)}")
    return None


def normalize_track(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if any(flag in text for flag in ["\u7269\u7406", "\u7406\u5de5", "\u7406\u79d1"]):
        return "physics"
    if any(flag in text for flag in ["\u5386\u53f2", "\u6587\u53f2", "\u6587\u79d1"]):
        return "history"
    if "\u7efc\u5408" in text:
        return "comprehensive"
    return text


def normalize_batch(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = text.replace("\u672c\u79d1\u6279", "\u672c\u79d1")
    text = text.replace("\u4e13\u79d1\u6279", "\u4e13\u79d1")
    return text


def normalize_school_name(value: Any) -> str:
    text = normalize_text(value)
    aliases = {
        "\u5409\u6797\u5927\u5b66(\u6297\u9707\u6551\u707e\u6821\u533a)": "\u5409\u6797\u5927\u5b66",
    }
    return aliases.get(text, text)


def normalize_major_name(value: Any) -> str:
    text = normalize_text(value)
    text = text.replace("\uff08", "(").replace("\uff09", ")")
    return text


def safe_slug(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text)
    return text.strip("_") or "sheet"


def discover_workbooks() -> dict[str, LocatedWorkbook]:
    targets = {
        "major_scores_2022_2025": "22-25\u5e74\u5168\u56fd\u9ad8\u6821\u5728\u5409\u6797\u7684\u4e13\u4e1a\u5f55\u53d6\u5206\u6570.xlsx",
        "school_scores_2022_2025": "22-25\u5e74\u5168\u56fd\u9ad8\u6821\u5728\u5409\u6797\u7684\u9662\u6821\u5f55\u53d6\u5206\u6570.xlsx",
        "plans_2022_2025": "22-25\u5e74\u5168\u56fd\u9ad8\u6821\u5728\u5409\u6797\u7701\u7684\u62db\u751f\u8ba1\u5212.xlsx",
        "score_rank_2017_2022": "\u5409\u6797_\u4e00\u5206\u4e00\u6bb5_2022_2017.xlsx",
        "control_lines_2014_2022": "_\u7701\u63a7\u7ebf_\u6279\u6b21\u7ebf_2022_2014.xlsx",
    }
    found: dict[str, LocatedWorkbook] = {}
    for path in LIBRARY_ROOT.rglob("*.xlsx"):
        for key, filename in targets.items():
            if path.name == filename:
                found[key] = LocatedWorkbook(key=key, path=path)
                break
    return found


def discover_score_rank_workbooks(workbooks: dict[str, LocatedWorkbook]) -> list[LocatedWorkbook]:
    located: list[LocatedWorkbook] = []
    score_rank_dir = (
        LIBRARY_ROOT
        / "17、吉林-2026志愿填报资料【永久更新】"
        / "2、吉林高考录取数据22-25【持续更新】"
        / "一分一段"
    )
    if score_rank_dir.exists():
        for path in sorted(score_rank_dir.glob("*.xlsx")):
            located.append(LocatedWorkbook(key=f"score_rank_{path.stem}", path=path))
    historical = workbooks.get("score_rank_2017_2022")
    if historical:
        located.append(historical)
    return located


def dump_workbook_preview(path: Path) -> list[dict[str, Any]]:
    workbook = pd.ExcelFile(path)
    previews: list[dict[str, Any]] = []
    for sheet_name in workbook.sheet_names:
        frame = workbook.parse(sheet_name, dtype=object)
        frame = frame.dropna(how="all")
        frame = frame.loc[:, ~frame.columns.astype(str).str.contains(r"^Unnamed")]
        preview_frame = frame.head(5).astype(object).where(pd.notna(frame.head(5)), "")
        preview_rows = preview_frame.to_dict(orient="records")
        previews.append(
            {
                "sheet_name": sheet_name,
                "row_count": int(frame.shape[0]),
                "columns": [normalize_text(col) for col in frame.columns.tolist()],
                "preview": preview_rows,
            }
        )
    return previews


def choose_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized_map = {normalize_text(col): col for col in columns}
    for candidate in candidates:
        for normalized, original in normalized_map.items():
            if candidate in normalized:
                return original
    return None


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(pd.notna(frame), "").to_dict(orient="records")


def normalize_major_rows(frame: pd.DataFrame, sheet_name: str) -> list[dict[str, Any]]:
    columns = [normalize_text(col) for col in frame.columns.tolist()]
    year_col = choose_column(columns, ["\u5e74", "\u5e74\u4efd"])
    school_col = choose_column(columns, ["\u9662\u6821"])
    major_col = choose_column(columns, ["\u4e13\u4e1a"])
    track_col = choose_column(columns, ["\u79d1\u7c7b", "\u9009\u79d1", "\u7c7b\u522b"])
    batch_col = choose_column(columns, ["\u6279\u6b21"])
    score_col = choose_column(columns, ["\u6700\u4f4e\u5206", "\u6295\u6863\u5206", "\u5f55\u53d6\u5206"])
    rank_col = choose_column(columns, ["\u6700\u4f4e\u4f4d\u6b21", "\u4f4d\u6b21"])
    plan_col = choose_column(columns, ["\u8ba1\u5212", "\u5f55\u53d6\u4eba\u6570"])
    city_col = choose_column(columns, ["\u57ce\u5e02", "\u6240\u5728\u5730"])
    level_col = choose_column(columns, ["\u9662\u6821\u5c42\u6b21", "\u529e\u5b66\u5c42\u6b21"])

    rows: list[dict[str, Any]] = []
    for raw in frame_records(frame):
        school = normalize_school_name(raw.get(school_col or "", ""))
        major = normalize_major_name(raw.get(major_col or "", ""))
        if not school:
            continue
        rows.append(
            {
                "data_year": normalize_year(raw.get(year_col or "", "")),
                "province": PROVINCE,
                "track": normalize_track(raw.get(track_col or "", "")),
                "batch": normalize_batch(raw.get(batch_col or "", "")),
                "school": school,
                "major": major,
                "city": normalize_text(raw.get(city_col or "", "")),
                "school_level": normalize_text(raw.get(level_col or "", "")),
                "min_score": normalize_int(raw.get(score_col or "", "")),
                "min_rank": normalize_int(raw.get(rank_col or "", "")),
                "plan_count": normalize_int(raw.get(plan_col or "", "")),
                "source_sheet": sheet_name,
            }
        )
    return rows


def normalize_school_rows(frame: pd.DataFrame, sheet_name: str) -> list[dict[str, Any]]:
    columns = [normalize_text(col) for col in frame.columns.tolist()]
    year_col = choose_column(columns, ["\u5e74", "\u5e74\u4efd"])
    school_col = choose_column(columns, ["\u9662\u6821"])
    track_col = choose_column(columns, ["\u79d1\u7c7b", "\u9009\u79d1", "\u7c7b\u522b"])
    batch_col = choose_column(columns, ["\u6279\u6b21"])
    score_col = choose_column(columns, ["\u6700\u4f4e\u5206", "\u6295\u6863\u5206", "\u5f55\u53d6\u5206"])
    rank_col = choose_column(columns, ["\u6700\u4f4e\u4f4d\u6b21", "\u4f4d\u6b21"])
    city_col = choose_column(columns, ["\u57ce\u5e02", "\u6240\u5728\u5730"])
    level_col = choose_column(columns, ["\u9662\u6821\u5c42\u6b21", "\u529e\u5b66\u5c42\u6b21"])

    rows: list[dict[str, Any]] = []
    for raw in frame_records(frame):
        school = normalize_school_name(raw.get(school_col or "", ""))
        if not school:
            continue
        rows.append(
            {
                "data_year": normalize_year(raw.get(year_col or "", "")),
                "province": PROVINCE,
                "track": normalize_track(raw.get(track_col or "", "")),
                "batch": normalize_batch(raw.get(batch_col or "", "")),
                "school": school,
                "city": normalize_text(raw.get(city_col or "", "")),
                "school_level": normalize_text(raw.get(level_col or "", "")),
                "min_score": normalize_int(raw.get(score_col or "", "")),
                "min_rank": normalize_int(raw.get(rank_col or "", "")),
                "source_sheet": sheet_name,
            }
        )
    return rows


def normalize_plan_rows(frame: pd.DataFrame, sheet_name: str) -> list[dict[str, Any]]:
    columns = [normalize_text(col) for col in frame.columns.tolist()]
    year_col = choose_column(columns, ["\u5e74", "\u5e74\u4efd"])
    school_col = choose_column(columns, ["\u9662\u6821"])
    major_col = choose_column(columns, ["\u4e13\u4e1a"])
    track_col = choose_column(columns, ["\u79d1\u7c7b", "\u9009\u79d1", "\u7c7b\u522b"])
    batch_col = choose_column(columns, ["\u6279\u6b21"])
    plan_col = choose_column(columns, ["\u8ba1\u5212", "\u62db\u751f\u4eba\u6570"])
    city_col = choose_column(columns, ["\u57ce\u5e02", "\u6240\u5728\u5730"])
    level_col = choose_column(columns, ["\u9662\u6821\u5c42\u6b21", "\u529e\u5b66\u5c42\u6b21"])
    tuition_col = choose_column(columns, ["\u5b66\u8d39"])

    rows: list[dict[str, Any]] = []
    for raw in frame_records(frame):
        school = normalize_school_name(raw.get(school_col or "", ""))
        major = normalize_major_name(raw.get(major_col or "", ""))
        if not school:
            continue
        rows.append(
            {
                "data_year": normalize_year(raw.get(year_col or "", "")),
                "province": PROVINCE,
                "track": normalize_track(raw.get(track_col or "", "")),
                "batch": normalize_batch(raw.get(batch_col or "", "")),
                "school": school,
                "major": major,
                "city": normalize_text(raw.get(city_col or "", "")),
                "school_level": normalize_text(raw.get(level_col or "", "")),
                "plan_count": normalize_int(raw.get(plan_col or "", "")),
                "tuition": normalize_text(raw.get(tuition_col or "", "")),
                "source_sheet": sheet_name,
            }
        )
    return rows


def normalize_score_rank_rows(frame: pd.DataFrame, sheet_name: str) -> list[dict[str, Any]]:
    columns = [normalize_text(col) for col in frame.columns.tolist()]
    year_col = choose_column(columns, ["\u5e74", "\u5e74\u4efd"])
    track_col = choose_column(columns, ["\u79d1\u7c7b", "\u7c7b\u522b", "\u6279\u7c7b"])
    score_col = choose_column(columns, ["\u5206\u6570"])
    rank_col = choose_column(columns, ["\u4f4d\u6b21", "\u540d\u6b21", "\u7d2f\u8ba1\u4eba\u6570"])

    rows: list[dict[str, Any]] = []
    for raw in frame_records(frame):
        score = normalize_int(raw.get(score_col or "", ""))
        rank = normalize_int(raw.get(rank_col or "", ""))
        if score is None or rank is None:
            continue
        rows.append(
            {
                "year": normalize_year(raw.get(year_col or "", "")),
                "province": PROVINCE,
                "track": normalize_track(raw.get(track_col or "", sheet_name)),
                "score": score,
                "rank": rank,
                "source_sheet": sheet_name,
            }
        )
    return rows


def normalize_control_line_rows(frame: pd.DataFrame, sheet_name: str) -> list[dict[str, Any]]:
    columns = [normalize_text(col) for col in frame.columns.tolist()]
    year_col = choose_column(columns, ["\u5e74", "\u5e74\u4efd"])
    track_col = choose_column(columns, ["\u79d1\u7c7b", "\u7c7b\u522b"])
    type_col = choose_column(columns, ["\u6279\u6b21", "\u7c7b\u578b", "\u5206\u6570\u7ebf"])
    score_col = choose_column(columns, ["\u5206\u6570", "\u5206\u6570\u7ebf"])

    rows: list[dict[str, Any]] = []
    for raw in frame_records(frame):
        score = normalize_int(raw.get(score_col or "", ""))
        if score is None:
            continue
        rows.append(
            {
                "year": normalize_year(raw.get(year_col or "", "")),
                "province": PROVINCE,
                "track": normalize_track(raw.get(track_col or "", sheet_name)),
                "line_type": normalize_text(raw.get(type_col or "", "")),
                "score": score,
                "source_sheet": sheet_name,
            }
        )
    return rows


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_workbook(path: Path, kind: str) -> list[dict[str, Any]]:
    workbook = pd.ExcelFile(path)
    all_rows: list[dict[str, Any]] = []
    for sheet_name in workbook.sheet_names:
        frame = workbook.parse(sheet_name, dtype=object)
        frame = frame.dropna(how="all")
        frame = frame.loc[:, ~frame.columns.astype(str).str.contains(r"^Unnamed")]
        if frame.empty:
            continue
        if kind == "major":
            rows = normalize_major_rows(frame, sheet_name)
        elif kind == "school":
            rows = normalize_school_rows(frame, sheet_name)
        elif kind == "plan":
            rows = normalize_plan_rows(frame, sheet_name)
        elif kind == "score_rank":
            rows = normalize_score_rank_rows(frame, sheet_name)
        elif kind == "control_line":
            rows = normalize_control_line_rows(frame, sheet_name)
        else:
            rows = []
        all_rows.extend(rows)
    return all_rows


def build_indexes(major_rows: list[dict[str, Any]], school_rows: list[dict[str, Any]], plan_rows: list[dict[str, Any]]) -> dict[str, Any]:
    school_index: dict[str, dict[str, Any]] = {}
    major_index: dict[str, dict[str, Any]] = {}

    for row in school_rows:
        school = row["school"]
        school_index.setdefault(
            school,
            {
                "school": school,
                "cities": set(),
                "levels": set(),
                "tracks": set(),
                "batches": set(),
                "years": set(),
            },
        )
        school_index[school]["cities"].add(row.get("city") or "")
        school_index[school]["levels"].add(row.get("school_level") or "")
        school_index[school]["tracks"].add(row.get("track") or "")
        school_index[school]["batches"].add(row.get("batch") or "")
        if row.get("data_year"):
            school_index[school]["years"].add(row["data_year"])

    for row in major_rows:
        major = row.get("major") or "\u672a\u5206\u4e13\u4e1a"
        major_index.setdefault(
            major,
            {
                "major": major,
                "schools": set(),
                "tracks": set(),
                "years": set(),
            },
        )
        major_index[major]["schools"].add(row["school"])
        major_index[major]["tracks"].add(row.get("track") or "")
        if row.get("data_year"):
            major_index[major]["years"].add(row["data_year"])

    for row in plan_rows:
        school = row["school"]
        school_index.setdefault(
            school,
            {
                "school": school,
                "cities": set(),
                "levels": set(),
                "tracks": set(),
                "batches": set(),
                "years": set(),
            },
        )
        school_index[school]["cities"].add(row.get("city") or "")
        school_index[school]["levels"].add(row.get("school_level") or "")
        school_index[school]["tracks"].add(row.get("track") or "")
        school_index[school]["batches"].add(row.get("batch") or "")
        if row.get("data_year"):
            school_index[school]["years"].add(row["data_year"])

    def serialize_index(source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for _, item in sorted(source.items()):
            rows.append(
                {
                    key: sorted(value) if isinstance(value, set) else value
                    for key, value in item.items()
                }
            )
        return rows

    return {
        "school_index": serialize_index(school_index),
        "major_index": serialize_index(major_index),
    }


def dedupe_rows(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        identity = tuple(row.get(key) for key in keys)
        deduped[identity] = row
    return list(deduped.values())


def main() -> None:
    workbooks = discover_workbooks()
    if not workbooks:
        raise SystemExit(f"No workbooks found under {LIBRARY_ROOT}")

    score_rank_workbooks = discover_score_rank_workbooks(workbooks)
    manifest: dict[str, Any] = {"library_root": str(LIBRARY_ROOT), "workbooks": {}, "score_rank_workbooks": []}
    for key, workbook in workbooks.items():
        previews = dump_workbook_preview(workbook.path)
        manifest["workbooks"][key] = {
            "path": str(workbook.path),
            "sheet_count": len(previews),
            "sheets": previews,
        }
        save_json(RAW_OUTPUT / f"{key}_preview.json", manifest["workbooks"][key])
    for workbook in score_rank_workbooks:
        previews = dump_workbook_preview(workbook.path)
        payload = {
            "path": str(workbook.path),
            "sheet_count": len(previews),
            "sheets": previews,
        }
        manifest["score_rank_workbooks"].append({"key": workbook.key, **payload})
        save_json(RAW_OUTPUT / f"{safe_slug(workbook.key)}_preview.json", payload)

    major_rows = normalize_workbook(workbooks["major_scores_2022_2025"].path, "major") if "major_scores_2022_2025" in workbooks else []
    school_rows = normalize_workbook(workbooks["school_scores_2022_2025"].path, "school") if "school_scores_2022_2025" in workbooks else []
    plan_rows = normalize_workbook(workbooks["plans_2022_2025"].path, "plan") if "plans_2022_2025" in workbooks else []
    score_rank_rows: list[dict[str, Any]] = []
    for workbook in score_rank_workbooks:
        score_rank_rows.extend(normalize_workbook(workbook.path, "score_rank"))
    control_line_rows = normalize_workbook(workbooks["control_lines_2014_2022"].path, "control_line") if "control_lines_2014_2022" in workbooks else []

    major_rows = dedupe_rows(major_rows, ["data_year", "track", "batch", "school", "major", "min_score", "min_rank"])
    school_rows = dedupe_rows(school_rows, ["data_year", "track", "batch", "school", "min_score", "min_rank"])
    plan_rows = dedupe_rows(plan_rows, ["data_year", "track", "batch", "school", "major", "plan_count", "tuition"])
    score_rank_rows = dedupe_rows(score_rank_rows, ["year", "track", "score"])
    control_line_rows = dedupe_rows(control_line_rows, ["year", "track", "line_type", "score"])

    save_json(NORMALIZED_OUTPUT / "jilin_major_baselines_2022_2025.json", major_rows)
    save_json(NORMALIZED_OUTPUT / "jilin_school_baselines_2022_2025.json", school_rows)
    save_json(NORMALIZED_OUTPUT / "jilin_enrollment_plans_2022_2025.json", plan_rows)
    save_json(NORMALIZED_OUTPUT / "jilin_score_rank_2017_2025.json", score_rank_rows)
    save_json(NORMALIZED_OUTPUT / "jilin_control_lines_2014_2022.json", control_line_rows)

    indexes = build_indexes(major_rows, school_rows, plan_rows)
    save_json(INDEX_OUTPUT / "jilin_school_index.json", indexes["school_index"])
    save_json(INDEX_OUTPUT / "jilin_major_index.json", indexes["major_index"])
    save_json(RAW_OUTPUT / "jilin_library_manifest.json", manifest)

    summary = {
        "major_rows": len(major_rows),
        "school_rows": len(school_rows),
        "plan_rows": len(plan_rows),
        "score_rank_rows": len(score_rank_rows),
        "control_line_rows": len(control_line_rows),
        "school_index_rows": len(indexes["school_index"]),
        "major_index_rows": len(indexes["major_index"]),
    }
    save_json(INDEX_OUTPUT / "jilin_library_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
