from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "gaokao" / "raw"
PROCESSED_DIR = ROOT / "data" / "gaokao" / "processed"
YEAR = 2025
PROVINCE = "吉林省"


def parse_score_rank_text(path: Path, track: str) -> list[dict[str, int | str]]:
    records: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or not re.match(r"^\d+", line):
            continue
        numbers = [int(value) for value in re.findall(r"\d+", line)]
        if len(numbers) < 2:
            continue
        base_score = numbers[0]
        ranks = numbers[1:]
        if base_score > 750 or len(ranks) > 10:
            continue
        offsets = list(range(9, -1, -1))[-len(ranks):]
        for offset, rank in zip(offsets, ranks):
            records[base_score + offset] = rank

    return [
        {
            "year": YEAR,
            "province": PROVINCE,
            "track": track,
            "score": score,
            "rank": records[score],
        }
        for score in sorted(records.keys(), reverse=True)
    ]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_control_lines() -> list[dict[str, object]]:
    return [
        {"year": YEAR, "province": PROVINCE, "track": "physics", "line_type": "special", "score": 479},
        {"year": YEAR, "province": PROVINCE, "track": "physics", "line_type": "undergraduate", "score": 340},
        {"year": YEAR, "province": PROVINCE, "track": "physics", "line_type": "specialty", "score": 160},
        {"year": YEAR, "province": PROVINCE, "track": "history", "line_type": "special", "score": 493},
        {"year": YEAR, "province": PROVINCE, "track": "history", "line_type": "undergraduate", "score": 384},
        {"year": YEAR, "province": PROVINCE, "track": "history", "line_type": "specialty", "score": 160},
    ]


def load_admission_baselines() -> list[dict[str, object]]:
    seed_path = RAW_DIR / "jilin_2025_admission_baselines.seed.json"
    extra_seed_path = RAW_DIR / "jilin_2025_admission_baselines.extra.seed.json"
    rows = json.loads(seed_path.read_text(encoding="utf-8"))
    if extra_seed_path.exists():
        rows.extend(json.loads(extra_seed_path.read_text(encoding="utf-8")))
    return rows


def load_direction_pool() -> list[dict[str, object]]:
    seed_path = RAW_DIR / "jilin_2025_direction_pool.seed.json"
    if not seed_path.exists():
        return []
    return json.loads(seed_path.read_text(encoding="utf-8"))


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    physics_rows = parse_score_rank_text(RAW_DIR / "jilin_2025_physics_score_rank.pdf.txt", "physics")
    history_rows = parse_score_rank_text(RAW_DIR / "jilin_2025_history_score_rank.pdf.txt", "history")
    admission_rows = load_admission_baselines()
    direction_pool_rows = load_direction_pool()

    write_csv(
        PROCESSED_DIR / "jilin_2025_score_rank_physics.csv",
        physics_rows,
        ["year", "province", "track", "score", "rank"],
    )
    write_csv(
        PROCESSED_DIR / "jilin_2025_score_rank_history.csv",
        history_rows,
        ["year", "province", "track", "score", "rank"],
    )
    write_csv(
        PROCESSED_DIR / "jilin_2025_admission_baselines.csv",
        admission_rows,
        [
            "data_year",
            "province",
            "track",
            "school",
            "major",
            "city",
            "school_level",
            "batch",
            "min_score",
            "major_tags",
            "notes",
            "source_name",
            "source_url",
        ],
    )
    with (PROCESSED_DIR / "jilin_2025_control_lines.json").open("w", encoding="utf-8") as fp:
        json.dump(build_control_lines(), fp, ensure_ascii=False, indent=2)
    with (PROCESSED_DIR / "jilin_2025_direction_pool.json").open("w", encoding="utf-8") as fp:
        json.dump(direction_pool_rows, fp, ensure_ascii=False, indent=2)

    print(f"built {len(physics_rows)} physics score-rank rows")
    print(f"built {len(history_rows)} history score-rank rows")
    print(f"built {len(admission_rows)} admission baseline rows")
    print(f"built {len(direction_pool_rows)} direction-pool rows")


if __name__ == "__main__":
    main()
