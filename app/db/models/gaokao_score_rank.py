from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GaokaoScoreRank(Base):
    __tablename__ = "gaokao_score_ranks"
    __table_args__ = (
        UniqueConstraint("year", "province", "track", "score", name="uq_gaokao_score_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    province: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
