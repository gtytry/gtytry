from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Manager(Base):
    __tablename__ = "managers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="manager")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("managers.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)
    sale_probability: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    strengths: Mapped[str] = mapped_column(Text)
    mistakes: Mapped[str] = mapped_column(Text)
    missed_opportunities: Mapped[str] = mapped_column(Text)
    recommendations: Mapped[str] = mapped_column(Text)
    criteria_scores: Mapped[str] = mapped_column(Text)
    raw_response: Mapped[str] = mapped_column(Text)
    ocr_text: Mapped[str] = mapped_column(Text)
    image_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    manager: Mapped[Manager] = relationship(back_populates="analyses")
