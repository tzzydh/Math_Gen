from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_tasks.id"), index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    pdf_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="reports")
    diagnostic_task = relationship("DiagnosticTask", back_populates="reports")
    order = relationship("Order", back_populates="reports")
    pdf_asset = relationship("Asset", back_populates="reports")
