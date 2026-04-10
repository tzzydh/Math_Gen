from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models.gaokao_admission_baseline import GaokaoAdmissionBaseline
from app.db.models.gaokao_control_line import GaokaoControlLine
from app.db.models.gaokao_score_rank import GaokaoScoreRank
from app.db.session import SessionLocal

PROCESSED_DIR = ROOT / "data" / "gaokao" / "processed"
YEAR = 2025
PROVINCE = "吉林省"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def main() -> None:
    session = SessionLocal()
    try:
        physics_rows = load_csv(PROCESSED_DIR / "jilin_2025_score_rank_physics.csv")
        history_rows = load_csv(PROCESSED_DIR / "jilin_2025_score_rank_history.csv")
        baseline_rows = load_csv(PROCESSED_DIR / "jilin_2025_admission_baselines.csv")
        control_lines = json.loads((PROCESSED_DIR / "jilin_2025_control_lines.json").read_text(encoding="utf-8"))

        session.execute(
            delete(GaokaoAdmissionBaseline).where(
                GaokaoAdmissionBaseline.data_year == YEAR,
                GaokaoAdmissionBaseline.province == PROVINCE,
            )
        )
        session.execute(
            delete(GaokaoControlLine).where(
                GaokaoControlLine.year == YEAR,
                GaokaoControlLine.province == PROVINCE,
            )
        )
        session.execute(
            delete(GaokaoScoreRank).where(
                GaokaoScoreRank.year == YEAR,
                GaokaoScoreRank.province == PROVINCE,
            )
        )
        session.commit()

        for row in physics_rows + history_rows:
            session.add(
                GaokaoScoreRank(
                    year=int(row["year"]),
                    province=row["province"],
                    track=row["track"],
                    score=int(row["score"]),
                    rank=int(row["rank"]),
                )
            )
        session.commit()

        score_rank_map = {
            (track, score): rank
            for track, score, rank in session.execute(
                select(GaokaoScoreRank.track, GaokaoScoreRank.score, GaokaoScoreRank.rank).where(
                    GaokaoScoreRank.year == YEAR,
                    GaokaoScoreRank.province == PROVINCE,
                )
            )
        }

        for row in control_lines:
            session.add(
                GaokaoControlLine(
                    year=int(row["year"]),
                    province=row["province"],
                    track=row["track"],
                    line_type=row["line_type"],
                    score=int(row["score"]),
                )
            )
        session.commit()

        for row in baseline_rows:
            min_score = int(row["min_score"])
            session.add(
                GaokaoAdmissionBaseline(
                    data_year=int(row["data_year"]),
                    province=row["province"],
                    track=row["track"],
                    school=row["school"],
                    major=row["major"],
                    city=row["city"],
                    school_level=row.get("school_level") or None,
                    batch=row.get("batch") or None,
                    min_score=min_score,
                    min_rank=score_rank_map.get((row["track"], min_score)),
                    major_tags=row.get("major_tags") or None,
                    notes=row.get("notes") or None,
                    source_name=row.get("source_name") or None,
                    source_url=row.get("source_url") or None,
                )
            )
        session.commit()

        print(f"imported {len(physics_rows) + len(history_rows)} score-rank rows")
        print(f"imported {len(control_lines)} control line rows")
        print(f"imported {len(baseline_rows)} admission baseline rows")
    finally:
        session.close()


if __name__ == "__main__":
    main()
