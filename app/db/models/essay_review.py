from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EssayReview(Base):
    __tablename__ = "essay_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    source_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)
    pdf_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    subject: Mapped[str] = mapped_column(String(32), default="chinese", nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    recognized_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    corrected_title: Mapped[str] = mapped_column(String(255), nullable=False)
    recognized_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(nullable=False)
    score_max: Mapped[int] = mapped_column(nullable=False, default=60)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="essay_reviews")
    source_asset = relationship("Asset", foreign_keys=[source_asset_id])
    pdf_asset = relationship("Asset", foreign_keys=[pdf_asset_id])
