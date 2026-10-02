"""Persisted anomaly flags. Detector: app/services/anomalies.py."""
import uuid
from datetime import date as date_cls

from sqlalchemy import Date, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    dimension: Mapped[str] = mapped_column(String(16), nullable=False)  # global|country|product
    dim_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date: Mapped[date_cls] = mapped_column(Date, nullable=False)
    observed: Mapped[float] = mapped_column(Double, nullable=False)
    expected: Mapped[float] = mapped_column(Double, nullable=False)
    deviation: Mapped[float] = mapped_column(Double, nullable=False)  # robust z-score
    method: Mapped[str] = mapped_column(String(64), nullable=False)
