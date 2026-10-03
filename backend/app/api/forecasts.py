"""Forecast jobs: launch (async), poll status, compare, capabilities."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import get_settings
from app.db.session import log_job_target, request_session, resolve_job_sync_url
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
    url, _source = resolve_job_sync_url(session.get_bind().url)
    return url


def _sync_target(session: AsyncSession) -> tuple[str, str]:
    """Return (sync_url, source) with safe-diagnostics source tracking."""
    return resolve_job_sync_url(session.get_bind().url)


def _train_and_release(slot: jobs.job_slot, **kwargs) -> None:
    try:
        train_group(**kwargs)
    finally:
        slot.__exit__(None, None, None)


def _inflight_filter(req: RunRequest):
    """Match groups for the same forecast key still in flight."""
    ctx = (ForecastGroup.context_id.is_(None) if req.context_id is None
           else ForecastGroup.context_id == req.context_id)
    return [ForecastGroup.dataset_id == req.dataset_id,
            ForecastGroup.target == req.target,
            ForecastGroup.context_type == req.context_type,
            ctx,
            ForecastGroup.horizon == req.horizon,
            ForecastGroup.status.in_(["pending", "running"])]


async def _find_inflight(session: AsyncSession, req: RunRequest):
    rows = (await session.execute(
        select(ForecastGroup).where(*_inflight_filter(req))
        .order_by(ForecastGroup.created_at.desc()))).scalars().all()
    return rows[0] if rows else None


@router.post("/runs", status_code=202)
async def create_run(req: RunRequest, background: BackgroundTasks,
                     session: AsyncSession = Depends(request_session)):
    ds = await session.get(Dataset, req.dataset_id)
    if ds is None:
        raise HTTPException(404, "dataset not found")
    if ds.status != "ready":
        # Datasets never mutate after ready, which is what makes the
        # result cache below safe; refuse to train on incomplete data.
        raise HTTPException(422, f"dataset is '{ds.status}'; forecast needs a ready dataset")
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

    # Identical-request cache + in-flight dedupe: a forecast is fully
    # identified by (dataset, target, context, horizon, model set), and
    # datasets are immutable once ready, so a completed group can be
    # returned instead of retraining all four models.
    inflight = await _find_inflight(session, req)
    if inflight is not None:
        return {"id": str(inflight.id), "status": inflight.status, "cached": False}
    prior = (await session.execute(
        select(ForecastGroup)
        .where(ForecastGroup.dataset_id == req.dataset_id,
               ForecastGroup.target == req.target,
               ForecastGroup.context_type == req.context_type,
               ForecastGroup.context_id.is_(None) if req.context_id is None
               else ForecastGroup.context_id == req.context_id,
               ForecastGroup.horizon == req.horizon,
               ForecastGroup.status == "done")
        .order_by(ForecastGroup.created_at.desc()))).scalars().all()
    for g in prior:
        done_models = sorted((await session.execute(
            select(ForecastRun.model).where(
                ForecastRun.group_id == g.id,
                ForecastRun.status == "done"))).scalars().all())
        if done_models == sorted(wanted):
            return {"id": str(g.id), "status": "done", "cached": True}

    slot = jobs.acquire_or_429()  # 429 instead of silently overloading the box
    group = ForecastGroup(dataset_id=req.dataset_id, target=req.target,
                          context_type=req.context_type, context_id=req.context_id,
                          horizon=req.horizon, status="pending")
    session.add(group)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a concurrent-insert race: the DB's partial unique index
        # (uq_forecast_groups_inflight) admitted only one pending/running
        # group per key. Release the slot and attach to the winner instead
        # of training twice.
        await session.rollback()
        slot.__exit__(None, None, None)
        winner = await _find_inflight(session, req)
        if winner is not None:
            return {"id": str(winner.id), "status": winner.status, "cached": False}
        raise HTTPException(409, "duplicate forecast request in flight; retry shortly")
    except Exception:
        # Any other insert failure must also release the slot, or capacity
        # leaks permanently (MAX_CONCURRENT_JOBS is tiny).
        await session.rollback()
        slot.__exit__(None, None, None)
        raise
    await session.refresh(group)
    sync_url, sync_source = _sync_target(session)
    log_job_target(sync_source, sync_url, f"forecast-{group.id}")
    background.add_task(_train_and_release, slot, group_id=group.id,
                        dataset_id=req.dataset_id, target=req.target,
                        context_type=req.context_type, context_id=req.context_id,
                        horizon=req.horizon, models=wanted,
                        sync_url=sync_url)
    return {"id": str(group.id), "status": "pending", "cached": False}


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
        sync_url, sync_source = _sync_target(session)
        df = load_series(ds.id, "global", None, horizon, sync_url, sync_source)
        info["global_points"] = len(df)
        info["history"] = {"from": df["date"].iloc[0].strftime("%Y-%m-%d"),
                           "to": df["date"].iloc[-1].strftime("%Y-%m-%d")}
        info["folds"] = len(expanding_folds(len(df), horizon))
    except InsufficientHistory as e:
        info["global_points"] = 0
        info["insufficient"] = str(e)
    return info
