from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

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

    assets = relationship("Asset", back_populates="user")
    diagnostic_tasks = relationship("DiagnosticTask", back_populates="user")
    orders = relationship("Order", back_populates="user")
    reports = relationship("Report", back_populates="user")
    essay_reviews = relationship("EssayReview", back_populates="user")
    gaokao_plans = relationship("GaokaoPlan", back_populates="user")
