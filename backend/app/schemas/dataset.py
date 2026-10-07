"""Pydantic DTOs. API speaks aggregates/profiles, never raw row dumps."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetOut(BaseModel):
    id: UUID
    filename: str
    status: str
    row_count: int
    date_from: datetime | None
    date_to: datetime | None
    schema_map: dict
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetStatusOut(BaseModel):
    """Lightweight polling DTO for async ingestion (no profile payload)."""

    id: UUID
    status: str
    error: str | None = None
    row_count: int = 0

    model_config = {"from_attributes": True}


class DatasetProfileOut(DatasetOut):
    profile: dict
    parquet_path: str
