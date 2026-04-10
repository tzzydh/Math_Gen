from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GaokaoPlan(Base):
    __tablename__ = "gaokao_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    province: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_combination: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[str] = mapped_column(String(32), nullable=False)
    rank: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="gaokao_plans")
