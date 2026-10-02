"""Supabase storage preflight: measure ACTUAL PostgreSQL storage.

Estimates nothing from row counts — every byte below comes from
PostgreSQL-native size functions against the live database:

    pg_database_size()         whole database on disk
    pg_total_relation_size()   table heap + indexes + TOAST, per table
    pg_relation_size()         table heap (data) only
    pg_indexes_size()          all indexes on the table

Usage (from backend/; DATABASE_URL selects the database to measure):

    python scripts/check_production_db_size.py
    DATABASE_URL='<supabase-direct>' python scripts/check_production_db_size.py

Exit code 0 when the database fits in Supabase Free (500 MB),
exit code 1 when it exceeds the quota. The script never modifies data.
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import make_job_engine, normalize_sync_url  # noqa: E402

# Fixed allowlist — table names are interpolated into SQL, so no caller
# input may ever reach this list.
MARTS = ["sales_daily", "sales_monthly", "product_daily",
         "product_summary", "country_daily", "customer_summary"]
FORECAST = ["forecast_groups", "forecast_runs", "forecast_points"]
ANOMALIES = ["anomalies"]
REGISTRY = ["datasets"]
TABLES = REGISTRY + MARTS + FORECAST + ANOMALIES

SUPABASE_FREE_BYTES = 500 * 1024 * 1024
WARN_PCT = 80.0


def human(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "kB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"  # unreachable; keeps type-checkers calm


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure actual PostgreSQL storage (preflight).")
    ap.parse_args()

    sync_url = normalize_sync_url(get_settings().database_url)
    host = sync_url.split("@")[-1]  # host/db only — never print credentials
    engine = make_job_engine(sync_url)
    try:
        with engine.connect() as conn:
            db_bytes = conn.execute(
                text("SELECT pg_database_size(current_database())")).scalar()
            db_name = conn.execute(text("SELECT current_database()")).scalar()

            print(f"database: {db_name}  (via {host})")
            print()
            print("DATASETS IN THIS DATABASE")
            regs = conn.execute(text(
                "SELECT filename, status, row_count FROM datasets "
                "ORDER BY created_at")).all()
            if not regs:
                print("  (no datasets)")
            for filename, status, row_count in regs:
                print(f"  {filename}  status={status}  rows={row_count:,}")
            print()

            print(f"{'TABLE':<28}{'ROWS':>12}{'DATA':>12}{'INDEXES':>12}{'TOTAL':>12}")
            print("-" * 76)
            group_totals: dict[str, list[int]] = {}
            for table in TABLES:
                n = conn.execute(
                    text(f"SELECT count(*) FROM {table}")).scalar() or 0
                data_b = conn.execute(
                    text(f"SELECT pg_relation_size('{table}')")).scalar() or 0
                idx_b = conn.execute(
                    text(f"SELECT pg_indexes_size('{table}')")).scalar() or 0
                tot_b = conn.execute(
                    text(f"SELECT pg_total_relation_size('{table}')")).scalar() or 0
                print(f"{table:<28}{n:>12,}{human(data_b):>12}"
                      f"{human(idx_b):>12}{human(tot_b):>12}")
                group = ("forecast_*" if table in FORECAST
                         else "anomaly_*" if table in ANOMALIES else None)
                if group:
                    g = group_totals.setdefault(group, [0, 0, 0, 0])
                    g[0] += n
                    g[1] += data_b
                    g[2] += idx_b
                    g[3] += tot_b
            for group, (n, data_b, idx_b, tot_b) in group_totals.items():
                print(f"{group:<28}{n:>12,}{human(data_b):>12}"
                      f"{human(idx_b):>12}{human(tot_b):>12}  (subtotal)")
            print("-" * 76)
            sum_data = conn.execute(text(
                "SELECT coalesce(sum(pg_relation_size(schemaname || '.' || tablename)), 0) "
                "FROM pg_tables WHERE schemaname = 'public'")).scalar() or 0
            sum_idx = conn.execute(text(
                "SELECT coalesce(sum(pg_indexes_size(schemaname || '.' || tablename)), 0) "
                "FROM pg_tables WHERE schemaname = 'public'")).scalar() or 0
            sum_total = sum_data + sum_idx
            print(f"{'TOTAL (all public tables)':<28}{'':>12}{human(sum_data):>12}"
                  f"{human(sum_idx):>12}{human(sum_total):>12}")
            print()

            print("LARGEST INDEXES (exact consumers)")
            idx_rows = conn.execute(text(
                "SELECT i.indexrelid::regclass::text, "
                "       pg_relation_size(i.indexrelid) AS b "
                "FROM pg_index i JOIN pg_class t ON t.oid = i.indrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE n.nspname = 'public' "
                "ORDER BY b DESC LIMIT 15")).all()
            for name, b in idx_rows:
                print(f"  {name:<52}{human(b):>12}")
            print()

            free = SUPABASE_FREE_BYTES
            used_pct = db_bytes / free * 100
            headroom = free - db_bytes
            print(f"DATABASE TOTAL:          {human(db_bytes)} ({db_bytes:,} bytes)")
            print(f"SUPABASE FREE LIMIT:     {human(free)} ({free:,} bytes)")
            print(f"REMAINING HEADROOM:      {human(headroom)} ({headroom:,} bytes)")
            print(f"HEADROOM %:              {100 - used_pct:.1f}% free "
                  f"({used_pct:.1f}% used)")
            print()
            if db_bytes > free:
                print(f"VERDICT: EXCEEDS quota by {human(db_bytes - free)} — "
                      "do NOT deploy seed as-is; add a larger database or a "
                      "retention strategy first. No data was touched.")
                return 1
            if used_pct >= WARN_PCT:
                print(f"VERDICT: APPROACHING quota ({used_pct:.1f}% used) — "
                      "fits today, but monitor growth before adding datasets. "
                      "No data was touched.")
                return 0
            print(f"VERDICT: FITS comfortably ({used_pct:.1f}% of quota used).")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
