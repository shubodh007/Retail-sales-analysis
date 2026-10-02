"""Analytical mart tables. Populated by Spark (see app/services/marts.py)."""
import uuid
from datetime import date as date_cls

from sqlalchemy import BigInteger, Date, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SalesDaily(Base):
    __tablename__ = "sales_daily"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date_cls] = mapped_column(Date, primary_key=True)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)


class SalesMonthly(Base):
    __tablename__ = "sales_monthly"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[date_cls] = mapped_column(Date, primary_key=True)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)


class ProductDaily(Base):
    __tablename__ = "product_daily"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date_cls] = mapped_column(Date, primary_key=True)
    stockcode: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProductSummary(Base):
    __tablename__ = "product_summary"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    stockcode: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
    last_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)


class CountryDaily(Base):
    __tablename__ = "country_daily"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date_cls] = mapped_column(Date, primary_key=True)
    country: Mapped[str] = mapped_column(Text, primary_key=True)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CustomerSummary(Base):
    __tablename__ = "customer_summary"
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="")
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    first_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
    last_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
