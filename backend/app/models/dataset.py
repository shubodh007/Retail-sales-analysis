"""Dataset registry. Raw rows live in Parquet; Postgres holds metadata + profile."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schema_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parquet_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Async ingestion: queued -> processing -> ready | failed. Human-readable
    # failure reason (exception type + message only, never a traceback).
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
