"""Forecast jobs: launch (async), poll status, compare, capabilities."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import get_settings
from app.db.session import request_session, sync_url_from_async
from app.forecast.estimators import MODELS
from app.forecast.interface import InsufficientHistory
from app.forecast.runner import train_group
from app.forecast.series import expanding_folds, load_series
from app.models.dataset import Dataset
from app.models.forecast import ForecastGroup, ForecastPoint, ForecastRun

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

HORIZONS = (7, 30, 90)


class RunRequest(BaseModel):
    dataset_id: uuid.UUID
    target: str = "revenue"
    context_type: str = "global"
    context_id: str | None = None
    horizon: int = 30
    models: list[str] | None = None  # None = auto (all feasible)


def _sync_url(session: AsyncSession) -> str:
    return sync_url_from_async(str(session.get_bind().url))


def _train_and_release(slot: jobs.job_slot, **kwargs) -> None:
    try:
        train_group(**kwargs)
    finally:
        slot.__exit__(None, None, None)


@router.post("/runs", status_code=202)
async def create_run(req: RunRequest, background: BackgroundTasks,
                     session: AsyncSession = Depends(request_session)):
    ds = await session.get(Dataset, req.dataset_id)
    if ds is None:
        raise HTTPException(404, "dataset not found")
    if req.target != "revenue":
        raise HTTPException(422, "Phase 3 supports target=revenue only")
    if req.context_type not in ("global", "product", "country"):
        raise HTTPException(422, "context must be global, product, or country")
    if req.horizon not in HORIZONS:
        raise HTTPException(422, f"horizon must be one of {HORIZONS}")
    if req.horizon > get_settings().max_forecast_horizon:
        raise HTTPException(
            422, f"horizon {req.horizon} exceeds this deployment's limit "
                 f"({get_settings().max_forecast_horizon} days)")
    wanted = req.models or list(MODELS)
    unknown = [m for m in wanted if m not in MODELS]
    if unknown:
        raise HTTPException(422, f"unknown models: {unknown}")
    if req.context_type != "global" and not req.context_id:
        raise HTTPException(422, "context_id required for product/country contexts")
    slot = jobs.acquire_or_429()  # 429 instead of silently overloading the box
    group = ForecastGroup(dataset_id=req.dataset_id, target=req.target,
                          context_type=req.context_type, context_id=req.context_id,
                          horizon=req.horizon, status="pending")
    session.add(group)
    await session.commit()
    await session.refresh(group)
    background.add_task(_train_and_release, slot, group_id=group.id,
                        dataset_id=req.dataset_id, target=req.target,
                        context_type=req.context_type, context_id=req.context_id,
                        horizon=req.horizon, models=wanted,
                        sync_url=_sync_url(session))
    return {"id": str(group.id), "status": "pending"}


def _run_dto(run: ForecastRun, points: list[ForecastPoint]) -> dict:
    return {
        "model": run.model, "status": run.status, "metrics": run.metrics,
        "mape_status": run.mape_status, "interval_type": run.interval_type,
        "config": run.config, "train_from": run.train_from, "train_to": run.train_to,
        "val_from": run.val_from, "val_to": run.val_to,
        "duration_s": round(run.duration_s, 1), "error": run.error,
        "history": [{"date": p.date, "actual": p.actual} for p in points if p.kind == "history"],
        "validation": [{"date": p.date, "actual": p.actual, "predicted": p.predicted}
                       for p in points if p.kind == "validation"],
        "forecast": [{"date": p.date, "predicted": p.predicted, "lower": p.lower, "upper": p.upper}
                     for p in points if p.kind == "forecast"],
    }


@router.get("/runs/{group_id}")
async def get_run(group_id: uuid.UUID, model: str | None = None,
                  session: AsyncSession = Depends(request_session)):
    group = await session.get(ForecastGroup, group_id)
    if group is None:
        raise HTTPException(404, "forecast group not found")
    runs = (await session.execute(
        select(ForecastRun).where(ForecastRun.group_id == group_id))).scalars().all()
    out = {"id": str(group.id), "status": group.status, "target": group.target,
           "context_type": group.context_type, "context_id": group.context_id,
           "horizon": group.horizon, "best_model": group.best_model,
           "selection_metric": group.selection_metric, "error": group.error,
           "created_at": group.created_at.isoformat() if group.created_at else None,
           "runs": []}
    for run in runs:
        if model and run.model != model:
            continue
        pts = (await session.execute(
            select(ForecastPoint).where(ForecastPoint.run_id == run.id)
            .order_by(ForecastPoint.date, ForecastPoint.id))).scalars().all()
        out["runs"].append(_run_dto(run, pts))
    return out


@router.get("/compare/{group_id}")
async def compare(group_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    group = await session.get(ForecastGroup, group_id)
    if group is None:
        raise HTTPException(404, "forecast group not found")
    runs = (await session.execute(
        select(ForecastRun).where(ForecastRun.group_id == group_id))).scalars().all()
    table = [{"model": r.model, "status": r.status, "metrics": r.metrics,
              "mape_status": r.mape_status, "duration_s": round(r.duration_s, 1)}
             for r in runs]
    return {
        "group_id": str(group.id), "status": group.status,
        "selection": {"metric": group.selection_metric, "best_model": group.best_model,
                      "criterion": "lowest validation WAPE (zero-safe); MAPE shown only when valid"},
        "models": table,
    }


@router.get("/capabilities")
async def fc_capabilities(dataset_id: uuid.UUID,
                          horizon: int = Query(30, description="planned horizon"),
                          session: AsyncSession = Depends(request_session)):
    ds = await session.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "dataset not found")
    from app.services import capabilities as caps
    have = caps.capabilities(ds.schema_map)
    info: dict = {"horizons": list(HORIZONS), "models": list(MODELS),
                  "selection_metric": "wape",
                  "contexts": {"global": {"supported": True}}}
    for ctx, role in (("product", "products"), ("country", "geography")):
        info["contexts"][ctx] = {"supported": bool(have.get(role))}
    try:
        df = load_series(ds.id, "global", None, horizon, _sync_url(session))
        info["global_points"] = len(df)
        info["history"] = {"from": df["date"].iloc[0].strftime("%Y-%m-%d"),
                           "to": df["date"].iloc[-1].strftime("%Y-%m-%d")}
        info["folds"] = len(expanding_folds(len(df), horizon))
    except InsufficientHistory as e:
        info["global_points"] = 0
        info["insufficient"] = str(e)
    return info
