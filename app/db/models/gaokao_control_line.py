from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GaokaoControlLine(Base):
    __tablename__ = "gaokao_control_lines"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "province",
            "track",
            "line_type",
            name="uq_gaokao_control_line",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    province: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    line_type: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
