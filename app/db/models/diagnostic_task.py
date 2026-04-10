from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DiagnosticTask(Base):
    __tablename__ = "diagnostic_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    ocr_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_points_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="diagnostic_tasks")
    asset = relationship("Asset", back_populates="diagnostic_tasks")
    orders = relationship("Order", back_populates="diagnostic_task")
    reports = relationship("Report", back_populates="diagnostic_task")
