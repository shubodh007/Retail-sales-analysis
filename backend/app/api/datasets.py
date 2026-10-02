"""Dataset upload/list/profile.

Upload is ASYNC by design (UCI-scale Spark profiling takes minutes):

    POST /datasets/upload -> 202 {"id", "status": "queued"}
    GET  /datasets/{id}/status -> {"id", "status", "error", ...}  (poll)
    queued -> processing -> ready | failed

Heavy work runs in a FastAPI BackgroundTasks worker thread bounded by the
single-process job gate (app.core.jobs). No Celery/Redis: one container,
one demo-scale workload — documented in docs/deployment.md.
"""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core import jobs
from app.core.config import get_settings
from app.db.session import make_job_engine, request_session, sync_url_from_async
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetOut, DatasetProfileOut, DatasetStatusOut
from app.services import mapping as mapping_svc
from app.services.anomalies import build_anomalies
from app.services.marts import build_marts
from app.services import profiling as profiling_svc

router = APIRouter(prefix="/datasets", tags=["datasets"])

log = logging.getLogger("retail-intelligence")

MAX_FILENAME_LEN = 200

TERMINAL = ("ready", "failed")


def _workspace() -> tuple[Path, Path]:
    """(staging, curated) dirs. UPLOAD_DIR/DATA_DIR override the dev default.

    Both are TEMPORARY processing space: the container filesystem is
    ephemeral and PostgreSQL is the authoritative store.
    """
    s = get_settings()
    if s.upload_dir:
        staging = Path(s.upload_dir)
    elif s.data_dir:
        staging = Path(s.data_dir) / "staging"
    else:
        staging = Path(__file__).resolve().parents[2] / "data_lake" / "staging"
    if s.data_dir:
        curated = Path(s.data_dir) / "curated"
    else:
        curated = Path(__file__).resolve().parents[2] / "data_lake" / "curated"
    staging.mkdir(parents=True, exist_ok=True)
    curated.mkdir(parents=True, exist_ok=True)
    return staging, curated


def _stage_paths(dataset_id: uuid.UUID, filename: str):
    staging, curated = _workspace()
    safe = Path(filename).name[:MAX_FILENAME_LEN]
    csv_path = staging / f"{dataset_id}__{safe}"
    parquet_path = curated / str(dataset_id)
    return csv_path, parquet_path


def _ingest_dataset(dataset_id: uuid.UUID, csv_path: str, parquet_path: str,
                    role_to_column: dict, filename: str, sync_url: str) -> None:
    """Background worker: Spark profile -> Parquet -> marts -> anomalies."""
    engine = make_job_engine(sync_url)
    Session = sessionmaker(engine, expire_on_commit=False)
    session = Session()
    t0 = datetime.now(timezone.utc)
    try:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            log.error("ingest %s: dataset row missing", dataset_id)
            return
        dataset.status = "processing"
        session.commit()

        profile = profiling_svc.profile_csv(csv_path, role_to_column, parquet_path)

        dataset.row_count = profile["row_count"]
        dataset.date_from = (datetime.fromisoformat(profile["date_from"])
                             if profile["date_from"] else None)
        dataset.date_to = (datetime.fromisoformat(profile["date_to"])
                           if profile["date_to"] else None)
        dataset.schema_map = dict(role_to_column)
        dataset.profile = dict(profile)
        dataset.parquet_path = str(parquet_path)
        flag_modified(dataset, "profile")
        session.commit()

        mart_counts = build_marts(dataset_id, parquet_path, role_to_column, sync_url)
        profile["marts"] = mart_counts
        anomaly_counts = build_anomalies(dataset_id, sync_url)
        profile["anomalies"] = anomaly_counts
        dataset.profile = dict(profile)
        dataset.status = "ready"
        dataset.error = None
        flag_modified(dataset, "profile")
        session.commit()
        log.info("ingest %s ready: rows=%s marts=%s anomalies=%s duration=%s",
                 dataset_id, profile["row_count"], mart_counts, anomaly_counts,
                 datetime.now(timezone.utc) - t0)
    except Exception as exc:
        # Type + message only: tracebacks would leak filesystem paths via API.
        reason = f"{type(exc).__name__}: {exc}"[:500]
        try:
            dataset = session.get(Dataset, dataset_id)
            if dataset is not None:
                dataset.status = "failed"
                dataset.error = reason
                session.commit()
        except Exception:
            session.rollback()
        log.warning("ingest %s failed: %s", dataset_id, reason)
    finally:
        session.close()
        engine.dispose()
        Path(csv_path).unlink(missing_ok=True)  # staging CSV is single-use


def _ingest_and_release(slot: jobs.job_slot, **kwargs) -> None:
    try:
        _ingest_dataset(**kwargs)
    finally:
        slot.__exit__(None, None, None)


@router.post("/upload", status_code=202)
async def upload_dataset(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(request_session),
):
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "only .csv uploads are supported in Phase 1")
    if len(Path(file.filename).name) > MAX_FILENAME_LEN:
        raise HTTPException(422, "filename too long")

    dataset_id = uuid.uuid4()
    csv_path, parquet_path = _stage_paths(dataset_id, file.filename)
    size = 0
    with open(csv_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                out.close()
                csv_path.unlink(missing_ok=True)
                raise HTTPException(413, f"file exceeds {settings.max_upload_mb} MB limit")
            out.write(chunk)
    if size == 0:
        csv_path.unlink(missing_ok=True)
        raise HTTPException(422, "empty file")

    headers = mapping_svc.read_headers(str(csv_path))
    if not headers:
        csv_path.unlink(missing_ok=True)
        raise HTTPException(422, "empty or headerless CSV")
    detected = mapping_svc.detect_mapping(headers)
    if detected.errors:
        csv_path.unlink(missing_ok=True)
        raise HTTPException(422, {"message": "schema validation failed",
                                  "errors": detected.errors})

    try:
        slot = jobs.acquire_or_429()  # raises 429 when all slots are busy
    except HTTPException:
        csv_path.unlink(missing_ok=True)
        raise
    dataset = Dataset(
        id=dataset_id,
        filename=Path(file.filename).name[:MAX_FILENAME_LEN],
        status="queued",
        row_count=0,
        schema_map=dict(detected.role_to_column),
        profile={},
        parquet_path="",
    )
    session.add(dataset)
    await session.commit()
    background.add_task(
        _ingest_and_release, slot,
        dataset_id=dataset_id, csv_path=str(csv_path), parquet_path=str(parquet_path),
        role_to_column=dict(detected.role_to_column), filename=dataset.filename,
        # Same database the request session is bound to (prod or test),
        # never a hardcoded URL.
        sync_url=sync_url_from_async(str(session.get_bind().url)),
    )
    log.info("upload %s queued: %s (%s bytes)", dataset_id, dataset.filename, size)
    return {"id": str(dataset_id), "status": "queued"}


@router.get("", response_model=list[DatasetOut])
async def list_datasets(session: AsyncSession = Depends(request_session)):
    rows = (await session.execute(select(Dataset).order_by(Dataset.created_at.desc()))).scalars()
    return list(rows)


@router.get("/{dataset_id}/status", response_model=DatasetStatusOut)
async def get_status(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    dataset = await session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")
    return dataset


@router.get("/{dataset_id}/profile", response_model=DatasetProfileOut)
async def get_profile(dataset_id: uuid.UUID, session: AsyncSession = Depends(request_session)):
    dataset = await session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")
    return dataset
