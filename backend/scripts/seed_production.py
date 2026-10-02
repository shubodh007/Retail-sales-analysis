"""Seed a fresh database (e.g. Supabase) with processed demo data.

Pipeline (deterministic, one-shot — NOT run on app startup):

    UCI Online Retail II canonical CSV (or the synthetic sample)
        -> validation -> PySpark profiling -> curated Parquet (temp)
        -> analytical marts -> anomalies -> PostgreSQL (Supabase)

Usage (from backend/ with DATABASE_URL pointing at the target database):

    python scripts/seed_production.py --csv ..\\datasets\\samples\\retail_synthetic.csv
    python scripts/seed_production.py --csv <path-to-online_retail_II.csv> --filename online_retail_II.csv

The script runs synchronously and exits; the deployed API then serves the
dashboard immediately from PostgreSQL with no further processing.
Requires the schema to exist: run ``alembic upgrade head`` first.
"""

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import make_job_engine, normalize_sync_url  # noqa: E402
from app.models.dataset import Dataset  # noqa: E402
from app.services import mapping as mapping_svc  # noqa: E402
from app.services.anomalies import build_anomalies  # noqa: E402
from app.services.marts import build_marts  # noqa: E402
from app.services import profiling as profiling_svc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed production DB with processed demo data.")
    ap.add_argument("--csv", required=True, help="Path to canonical retail CSV.")
    ap.add_argument("--filename", default=None, help="Display filename (default: CSV basename).")
    ap.add_argument("--workspace", default=None,
                    help="Temp dir for staging/parquet (default: backend/data_lake).")
    args = ap.parse_args()

    csv_src = Path(args.csv)
    if not csv_src.is_file():
        print(f"CSV not found: {csv_src}", file=sys.stderr)
        return 2
    display_name = args.filename or csv_src.name

    settings = get_settings()
    sync_url = normalize_sync_url(settings.database_url)
    print(f"target: {sync_url.split('@')[-1]}")  # host/db only, never credentials

    work = Path(args.workspace) if args.workspace else BACKEND_DIR / "data_lake"
    staging, curated = work / "staging", work / "curated"
    staging.mkdir(parents=True, exist_ok=True)
    curated.mkdir(parents=True, exist_ok=True)

    headers = mapping_svc.read_headers(str(csv_src))
    detected = mapping_svc.detect_mapping(headers)
    if detected.errors:
        print(f"schema validation failed: {detected.errors}", file=sys.stderr)
        return 2

    dataset_id = uuid.uuid4()
    staged = staging / f"{dataset_id}__{Path(display_name).name}"
    staged.write_bytes(csv_src.read_bytes())
    parquet_path = curated / str(dataset_id)

    print(f"profiling {display_name} (dataset {dataset_id}) ...")
    profile = profiling_svc.profile_csv(
        str(staged), dict(detected.role_to_column), str(parquet_path))

    engine = make_job_engine(sync_url)
    Session = sessionmaker(engine, expire_on_commit=False)
    session = Session()
    try:
        dataset = Dataset(
            id=dataset_id,
            filename=Path(display_name).name,
            status="processing",
            row_count=profile["row_count"],
            date_from=(datetime.fromisoformat(profile["date_from"])
                       if profile["date_from"] else None),
            date_to=(datetime.fromisoformat(profile["date_to"])
                     if profile["date_to"] else None),
            schema_map=dict(detected.role_to_column),
            profile=dict(profile),
            parquet_path=str(parquet_path),
        )
        session.add(dataset)
        session.commit()

        print("building marts ...")
        mart_counts = build_marts(dataset_id, str(parquet_path),
                                  dict(detected.role_to_column), sync_url)
        print(f"marts: {mart_counts}")
        print("building anomalies ...")
        anomaly_counts = build_anomalies(dataset_id, sync_url)
        print(f"anomalies: {anomaly_counts}")

        profile["marts"] = mart_counts
        profile["anomalies"] = anomaly_counts
        dataset.profile = dict(profile)
        dataset.status = "ready"
        session.commit()
        print(f"seeded dataset {dataset_id} ({display_name}): "
              f"rows={profile['row_count']} accepted={profile['quality']['accepted']}")
    finally:
        session.close()
        engine.dispose()
        staged.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
