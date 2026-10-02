"""Aggregated analytics over mart tables. Never raw rows; capability-gated."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import request_session
from app.models.anomaly import Anomaly
from app.models.dataset import Dataset
from app.models.marts import (CountryDaily, CustomerSummary, ProductDaily, ProductSummary,
                              SalesDaily, SalesMonthly)
from app.services import capabilities as caps

router = APIRouter(prefix="/analytics", tags=["analytics"])

SERIES_CAP = 1500
PAGE_MAX = 500


async def _dataset(session: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    ds = await session.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "dataset not found")
    return ds


def _gate(ds: Dataset, *need: str) -> None:
    reason = caps.require(ds.schema_map, *need)
    if reason:
        raise HTTPException(409, {"message": "unsupported dimension", "reason": reason})


@router.get("/overview")
async def overview(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "sales")
    totals = (await session.execute(
        select(func.sum(SalesDaily.revenue), func.sum(SalesDaily.qty),
               func.sum(SalesDaily.orders)).where(SalesDaily.dataset_id == ds.id)
    )).one()
    series = (await session.execute(
        select(SalesDaily.date, SalesDaily.revenue, SalesDaily.qty, SalesDaily.orders)
        .where(SalesDaily.dataset_id == ds.id).order_by(SalesDaily.date).limit(SERIES_CAP)
    )).all()
    top_products = (await session.execute(
        select(ProductSummary.stockcode, ProductSummary.description, ProductSummary.revenue,
               ProductSummary.qty).where(ProductSummary.dataset_id == ds.id)
        .order_by(desc(ProductSummary.revenue)).limit(5)
    )).all()
    geo: list = []
    if caps.capabilities(ds.schema_map)["geography"]:
        geo = (await session.execute(
            select(CountryDaily.country, func.sum(CountryDaily.revenue).label("revenue"),
                   func.sum(CountryDaily.qty).label("qty"))
            .where(CountryDaily.dataset_id == ds.id).group_by(CountryDaily.country)
            .order_by(desc("revenue")).limit(8)
        )).all()
    n_products = (await session.execute(
        select(func.count()).select_from(ProductSummary)
        .where(ProductSummary.dataset_id == ds.id))).scalar()
    return {
        "dataset": {"id": str(ds.id), "filename": ds.filename,
                    "capabilities": caps.capabilities(ds.schema_map)},
        "totals": {"revenue": totals[0] or 0.0, "qty": totals[1] or 0,
                   "orders": totals[2] or 0, "products": n_products or 0},
        "daily": [{"date": str(r[0]), "revenue": r[1], "qty": r[2], "orders": r[3]} for r in series],
        "top_products": [{"stockcode": r[0], "description": r[1], "revenue": r[2], "qty": r[3]}
                         for r in top_products],
        "top_countries": [{"country": r[0], "revenue": r[1], "qty": r[2]} for r in geo],
        "quality": ds.profile.get("quality", {}),
    }


@router.get("/sales/trend")
async def sales_trend(
    dataset_id: uuid.UUID,
    grain: str = Query("daily", pattern="^(daily|monthly)$"),
    country: str | None = None,
    session: AsyncSession = Depends(request_session),
):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "sales", *(["geography"] if country else []))
    if country:
        rows = (await session.execute(
            select(CountryDaily.date, CountryDaily.revenue, CountryDaily.qty, CountryDaily.orders)
            .where(CountryDaily.dataset_id == ds.id, CountryDaily.country == country)
            .order_by(CountryDaily.date).limit(SERIES_CAP))).all()
        return {"grain": grain, "country": country,
                "points": [{"date": str(r[0]), "revenue": r[1], "qty": r[2], "orders": r[3]}
                           for r in rows]}
    table = SalesDaily if grain == "daily" else SalesMonthly
    col = table.date if grain == "daily" else table.month
    rows = (await session.execute(
        select(col, table.revenue, table.qty, table.orders)
        .where(table.dataset_id == ds.id).order_by(col).limit(SERIES_CAP))).all()
    return {"grain": grain,
            "points": [{"date": str(r[0]), "revenue": r[1], "qty": r[2], "orders": r[3]} for r in rows]}


@router.get("/products")
async def products(
    dataset_id: uuid.UUID,
    sort: str = Query("revenue", pattern="^(revenue|qty|orders)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    session: AsyncSession = Depends(request_session),
):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "products")
    col = {"revenue": ProductSummary.revenue, "qty": ProductSummary.qty,
           "orders": ProductSummary.orders}[sort]
    stmt = select(ProductSummary).where(ProductSummary.dataset_id == ds.id)
    if search:
        stmt = stmt.where(ProductSummary.stockcode.ilike(f"%{search}%") |
                          ProductSummary.description.ilike(f"%{search}%"))
    total = (await session.execute(
        select(func.count()).select_from(stmt.subquery()))).scalar()
    stmt = stmt.order_by(desc(col) if direction == "desc" else col).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return {"total": total or 0, "limit": limit, "offset": offset, "items": [
        {"stockcode": r.stockcode, "description": r.description, "qty": r.qty,
         "revenue": r.revenue, "orders": r.orders,
         "first_date": str(r.first_date) if r.first_date else None,
         "last_date": str(r.last_date) if r.last_date else None} for r in rows]}


@router.get("/products/{stockcode}/trend")
async def product_trend(dataset_id: uuid.UUID, stockcode: str,
                        session: AsyncSession = Depends(request_session)):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "products")
    rows = (await session.execute(
        select(ProductDaily.date, ProductDaily.revenue, ProductDaily.qty)
        .where(ProductDaily.dataset_id == ds.id, ProductDaily.stockcode == stockcode)
        .order_by(ProductDaily.date).limit(SERIES_CAP))).all()
    if not rows:
        raise HTTPException(404, "product not found in this dataset")
    return {"stockcode": stockcode,
            "points": [{"date": str(r[0]), "revenue": r[1], "qty": r[2]} for r in rows]}


@router.get("/geography")
async def geography(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "geography")
    totals = (await session.execute(
        select(CountryDaily.country, func.sum(CountryDaily.revenue).label("revenue"),
               func.sum(CountryDaily.qty).label("qty"),
               func.sum(CountryDaily.orders).label("orders"))
        .where(CountryDaily.dataset_id == ds.id).group_by(CountryDaily.country)
        .order_by(desc("revenue")))).all()
    top = [r[0] for r in totals[:5]]
    daily = (await session.execute(
        select(CountryDaily.date, CountryDaily.country, CountryDaily.revenue)
        .where(CountryDaily.dataset_id == ds.id, CountryDaily.country.in_(top))
        .order_by(CountryDaily.date).limit(SERIES_CAP))).all() if top else []
    return {
        "countries": [{"country": r[0], "revenue": r[1], "qty": r[2], "orders": r[3]} for r in totals],
        "top_daily": [{"date": str(r[0]), "country": r[1], "revenue": r[2]} for r in daily],
    }


@router.get("/customers")
async def customers(
    dataset_id: uuid.UUID,
    sort: str = Query("revenue", pattern="^(revenue|qty|orders)$"),
    limit: int = Query(50, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(request_session),
):
    ds = await _dataset(session, dataset_id)
    _gate(ds, "customers")
    col = {"revenue": CustomerSummary.revenue, "qty": CustomerSummary.qty,
           "orders": CustomerSummary.orders}[sort]
    total = (await session.execute(
        select(func.count()).select_from(CustomerSummary)
        .where(CustomerSummary.dataset_id == ds.id))).scalar()
    rows = (await session.execute(
        select(CustomerSummary).where(CustomerSummary.dataset_id == ds.id)
        .order_by(desc(col)).offset(offset).limit(limit))).scalars().all()
    return {"total": total or 0, "limit": limit, "offset": offset, "items": [
        {"customer_id": r.customer_id, "country": r.country, "orders": r.orders,
         "qty": r.qty, "revenue": r.revenue} for r in rows]}


@router.get("/capabilities")
async def dataset_capabilities(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    ds = await _dataset(session, dataset_id)
    return {"dataset_id": str(ds.id), "capabilities": caps.capabilities(ds.schema_map)}


@router.get("/anomalies")
async def anomalies(
    dataset_id: uuid.UUID,
    dimension: str = Query("global", pattern="^(global|country|product)$"),
    key: str | None = None,
    limit: int = Query(100, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(request_session),
):
    ds = await _dataset(session, dataset_id)
    if dimension != "global":
        _gate(ds, "products" if dimension == "product" else "geography")
    stmt = select(Anomaly).where(Anomaly.dataset_id == ds.id, Anomaly.dimension == dimension)
    if key:
        stmt = stmt.where(Anomaly.dim_key == key)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    rows = (await session.execute(
        stmt.order_by(desc(Anomaly.deviation)).offset(offset).limit(limit))).scalars().all()
    return {"total": total or 0, "limit": limit, "offset": offset,
            "method": "trailing_median_mad_28 (|z| >= 3.5, 28-day trailing window)",
            "language": "Flags mark values associated with unusual movement — never a cause.",
            "items": [{"date": str(r.date), "dimension": r.dimension, "key": r.dim_key,
                       "observed": r.observed, "expected": round(r.expected, 2),
                       "deviation": round(r.deviation, 2)} for r in rows]}


@router.get("/anomalies/summary")
async def anomalies_summary(dataset_id: uuid.UUID,
                            session: AsyncSession = Depends(request_session)):
    ds = await _dataset(session, dataset_id)
    rows = (await session.execute(
        select(Anomaly.dimension, func.count()).where(Anomaly.dataset_id == ds.id)
        .group_by(Anomaly.dimension))).all()
    latest = (await session.execute(
        select(Anomaly).where(Anomaly.dataset_id == ds.id)
        .order_by(desc(Anomaly.deviation)).limit(5))).scalars().all()
    return {"by_dimension": {r[0]: r[1] for r in rows},
            "latest": [{"date": str(r.date), "dimension": r.dimension, "key": r.dim_key,
                        "observed": r.observed, "deviation": round(r.deviation, 2)} for r in latest]}


@router.get("/customers/rfm")
async def customers_rfm(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    from app.services import rfm as rfm_svc

    ds = await _dataset(session, dataset_id)
    _gate(ds, "customers")
    rows = (await session.execute(
        select(CustomerSummary).where(CustomerSummary.dataset_id == ds.id))).scalars().all()
    end = ds.date_to.date() if ds.date_to else None
    customers = [{"customer_id": r.customer_id, "country": r.country, "orders": r.orders,
                  "revenue": r.revenue, "last_date": r.last_date} for r in rows]
    out = rfm_svc.compute_rfm(customers, end) if end else {"segments": [], "customers": []}
    out["customers_total"] = len(out["customers"])
    out["customers"] = out["customers"][:100]  # aggregates cover the whole base; list is a sample
    for c in out["customers"]:
        c["last_date"] = str(c["last_date"]) if c["last_date"] else None
    out["methodology"] = {
        "recency": "dataset_end - last purchase (days); score 5 = most recent quintile",
        "frequency": "order count quintile", "monetary": "revenue quintile",
        "segments": "first-match rules: New(F==1) > Champions(R>=4,F>=4) > "
                    "At-risk(R<=2,F>=3) > Loyal(F>=4) > Promising(R>=4) > "
                    "Hibernating(R<=2) > Steady",
        "note": "Rule-based by design (auditable at this scale); no clustering, no invented attributes.",
    }
    return out
