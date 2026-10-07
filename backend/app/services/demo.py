"""Fresh-database bootstrap for the repository's real demo dataset.

The bootstrap is intentionally idempotent and runs in a worker thread during
application startup. It uses the same mapping, Spark profile, Parquet, marts,
and anomaly services as a user upload; it never supplies synthetic metrics.
"""
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.session import make_job_engine, normalize_sync_url
from app.models.dataset import Dataset
from app.services import mapping as mapping_svc
from app.services.anomalies import build_anomalies
from app.services.marts import build_marts
from app.services import profiling as profiling_svc

log = logging.getLogger("retail-intelligence")


def _demo_source() -> Path | None:
    configured = os.environ.get("DEMO_DATASET_PATH")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "datasets" / "demo" / "retail_sales_dataset_2.csv"
    return candidate if candidate.is_file() else None


def seed_demo_if_needed() -> None:
    """Seed the canonical demo once when no ready copy exists."""
    source = _demo_source()
    if source is None:
        log.info("demo bootstrap skipped: no DEMO_DATASET_PATH or bundled demo CSV")
        return

    settings = get_settings()
    sync_url = normalize_sync_url(settings.database_url)
    engine = make_job_engine(sync_url)
    Session = sessionmaker(engine, expire_on_commit=False)
    session = Session()
    staged: Path | None = None
    try:
        filename = source.name
        existing = (session.query(Dataset)
                    .filter(Dataset.filename == filename)
                    .order_by(Dataset.created_at.desc()).first())
        if existing and existing.status in {"queued", "processing", "ready"}:
            log.info("demo bootstrap skipped: %s already %s", filename, existing.status)
            return

        headers = mapping_svc.read_headers(str(source))
        detected = mapping_svc.detect_mapping(headers)
        if detected.errors:
            log.error("demo bootstrap rejected %s: %s", filename, detected.errors)
            return

        workspace = Path(settings.data_dir) if settings.data_dir else Path(__file__).resolve().parents[2] / "data_lake"
        staging, curated = workspace / "staging", workspace / "curated"
        staging.mkdir(parents=True, exist_ok=True)
        curated.mkdir(parents=True, exist_ok=True)
        dataset_id = uuid.uuid4()
        staged = staging / f"{dataset_id}__{filename}"
        parquet = curated / str(dataset_id)
        shutil.copyfile(source, staged)

        dataset = Dataset(id=dataset_id, filename=filename, status="processing",
                          row_count=0, schema_map=dict(detected.role_to_column),
                          profile={}, parquet_path=str(parquet))
        session.add(dataset)
        session.commit()
        profile = profiling_svc.profile_csv(str(staged), dict(detected.role_to_column), str(parquet))
        dataset.row_count = profile["row_count"]
        dataset.date_from = datetime.fromisoformat(profile["date_from"]) if profile["date_from"] else None
        dataset.date_to = datetime.fromisoformat(profile["date_to"]) if profile["date_to"] else None
        dataset.schema_map = dict(detected.role_to_column)
        dataset.profile = dict(profile)
        dataset.parquet_path = str(parquet)
        session.commit()

        marts = build_marts(dataset_id, str(parquet), dict(detected.role_to_column), sync_url)
        anomalies = build_anomalies(dataset_id, sync_url)
        profile["marts"] = marts
        profile["anomalies"] = anomalies
        dataset.profile = dict(profile)
        dataset.status = "ready"
        dataset.error = None
        session.commit()
        log.info("demo bootstrap ready: %s rows=%s marts=%s", filename, profile["row_count"], marts)
    except Exception as exc:
        session.rollback()
        log.exception("demo bootstrap failed: %s", exc)
    finally:
        session.close()
        engine.dispose()
        if staged is not None:
            staged.unlink(missing_ok=True)