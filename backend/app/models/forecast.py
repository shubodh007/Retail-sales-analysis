"""Forecast persistence: groups (one job) -> runs (one model) -> points."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ForecastGroup(Base):
    __tablename__ = "forecast_groups"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    target: Mapped[str] = mapped_column(String(32), nullable=False, default="revenue")
    context_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    context_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    best_model: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selection_metric: Mapped[str] = mapped_column(String(32), nullable=False, default="wape")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecast_groups.id", ondelete="CASCADE"), nullable=False)
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mape_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    interval_type: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    train_from: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    train_to: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    val_from: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    val_to: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    duration_s: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # history|validation|forecast
    actual: Mapped[float | None] = mapped_column(Double, nullable=True)
    predicted: Mapped[float | None] = mapped_column(Double, nullable=True)
    lower: Mapped[float | None] = mapped_column(Double, nullable=True)
    upper: Mapped[float | None] = mapped_column(Double, nullable=True)
