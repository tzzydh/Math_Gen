from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GaokaoAdmissionBaseline(Base):
    __tablename__ = "gaokao_admission_baselines"
    __table_args__ = (
        UniqueConstraint(
            "data_year",
            "province",
            "track",
            "school",
            "major",
            name="uq_gaokao_admission_baseline",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    data_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    province: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    school: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    major: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    school_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    batch: Mapped[str | None] = mapped_column(String(32), nullable=True)
    min_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    min_rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    major_tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
