"""Forecast baseline benchmark. Measures the CURRENT implementation.

Stages timed separately with time.perf_counter():
  series loading (load_series), feature construction (build_frame),
  per-model fit_predict (arima/prophet/rf/xgb x horizons 7/30/90),
  end-to-end train_group (rf-only, 7d) to observe persistence overhead.

Also counts (exact, via wrappers — not guesses):
  fit_predict calls, validation folds, feature-frame constructions,
  database series loads.

Usage (from backend/, dev DB must hold a READY dataset):
    python scripts/bench_forecast.py [--dataset-id <uuid>] [--out docs/forecast-baseline.json]

Benchmark train_group rows are deleted afterwards (cascade).
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import make_job_engine, normalize_sync_url  # noqa: E402
from app.forecast import estimators as EST  # noqa: E402
from app.forecast import features as FEAT  # noqa: E402
from app.forecast.series import expanding_folds, load_series  # noqa: E402
import app.models.anomaly  # noqa: F401,E402 (register tables for FK resolution)
import app.models.dataset  # noqa: F401,E402
import app.models.marts  # noqa: F401,E402
from app.models.forecast import ForecastGroup  # noqa: E402

DATASET_ID = "d0793ce2-624c-465d-88ab-cb8018a2c489"  # local UCI, ready


def pick_context(sync_url: str, ds: uuid.UUID):
    """Top-revenue product and country with >= 60 daily points (for 30d)."""
    engine = make_job_engine(sync_url)
    with engine.connect() as conn:
        prod = conn.execute(text(
            "SELECT stockcode FROM product_daily WHERE dataset_id=:d "
            "GROUP BY stockcode HAVING count(*) >= 60 "
            "ORDER BY sum(revenue) DESC LIMIT 1"), {"d": str(ds)}).scalar()
        country = conn.execute(text(
            "SELECT country FROM country_daily WHERE dataset_id=:d "
            "GROUP BY country HAVING count(*) >= 60 "
            "ORDER BY sum(revenue) DESC LIMIT 1"), {"d": str(ds)}).scalar()
    engine.dispose()
    return prod, country


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-id", default=DATASET_ID)
    ap.add_argument("--out", default="docs/forecast-baseline.json")
    args = ap.parse_args()

    ds = uuid.UUID(args.dataset_id)
    sync_url = normalize_sync_url(get_settings().database_url)

    counters = {"frames": 0, "fit_predict": 0, "series_loads": 0}
    orig_frame = EST.build_frame
    orig_fit_predict = EST.fit_predict

    def counted_frame(dates, y):
        counters["frames"] += 1
        return orig_frame(dates, y)

    def counted_fit_predict(model, df, horizon):
        counters["fit_predict"] += 1
        return orig_fit_predict(model, df, horizon)

    EST.build_frame = counted_frame
    EST.fit_predict = counted_fit_predict
    import app.forecast.runner as RUNNER
    RUNNER.fit_predict = counted_fit_predict
    # runner imports fit_predict by name: rebind not enough for `from` import?
    # runner.py does `from app.forecast.estimators import fit_predict`, so patch there too.
    from app.forecast import runner as _R  # noqa: E402
    _R.fit_predict = counted_fit_predict

    results: dict = {"dataset": str(ds), "stages": {}, "calls": []}
    try:
        # --- series loading ---
        t0 = time.perf_counter()
        df_g = load_series(ds, "global", None, 7, sync_url)
        counters["series_loads"] += 1
        t_load_g = time.perf_counter() - t0
        results["stages"]["load_global"] = round(t_load_g, 2)
        results["global_points"] = len(df_g)

        prod, country = pick_context(sync_url, ds)
        results["product_ctx"] = prod
        results["country_ctx"] = country
        for ctx, cid, h in (("product", prod, 30), ("country", country, 30)):
            t0 = time.perf_counter()
            df = load_series(ds, ctx, cid, h, sync_url)
            counters["series_loads"] += 1
            results["stages"][f"load_{ctx}_30"] = round(time.perf_counter() - t0, 2)
            results[f"{ctx}_points"] = len(df)

        # --- feature construction (single frame) ---
        t0 = time.perf_counter()
        frame = orig_frame(df_g["date"], df_g["y"])
        results["stages"]["build_frame_once"] = round(time.perf_counter() - t0, 3)
        results["frame_rows"] = len(frame)

        # --- per-model fits across horizons (global) ---
        for horizon in (7, 30, 90):
            df = load_series(ds, "global", None, horizon, sync_url)
            counters["series_loads"] += 1
            folds = expanding_folds(len(df), horizon)
            results.setdefault("folds", {})[str(horizon)] = len(folds)
            for model in ("arima", "prophet", "rf", "xgb"):
                before = dict(counters)
                t0 = time.perf_counter()
                try:
                    res = counted_fit_predict(model, df, horizon)
                    ok = True
                    wape = res.metrics.get("wape")
                except Exception as e:  # noqa: BLE001 - benchmark must continue
                    ok = False
                    wape = f"FAILED:{type(e).__name__}"
                dt = time.perf_counter() - t0
                results["calls"].append({
                    "context": "global", "horizon": horizon, "model": model,
                    "seconds": round(dt, 1), "ok": ok, "wape": wape,
                    "frames_built": counters["frames"] - before["frames"],
                })
                print(f"global h={horizon} {model}: {dt:.1f}s ok={ok} "
                      f"wape={wape} frames={counters['frames'] - before['frames']}",
                      flush=True)

        # --- ML on product/country contexts (30d, rf representative) ---
        for ctx, cid in (("product", prod), ("country", country)):
            df = load_series(ds, ctx, cid, 30, sync_url)
            counters["series_loads"] += 1
            before = dict(counters)
            t0 = time.perf_counter()
            res = counted_fit_predict("rf", df, 30)
            dt = time.perf_counter() - t0
            results["calls"].append({
                "context": ctx, "horizon": 30, "model": "rf",
                "seconds": round(dt, 1), "ok": True, "wape": res.metrics.get("wape"),
                "frames_built": counters["frames"] - before["frames"],
            })
            print(f"{ctx} h=30 rf: {dt:.1f}s wape={res.metrics.get('wape')} "
                  f"frames={counters['frames'] - before['frames']}", flush=True)

        # --- end-to-end (rf-only 7d) to observe runner + persistence overhead ---
        from app.forecast.runner import train_group  # noqa: E402
        gid = uuid.uuid4()
        engine = make_job_engine(sync_url)
        Session = sessionmaker(engine, expire_on_commit=False)
        s = Session()
        s.add(ForecastGroup(id=gid, dataset_id=ds, target="revenue",
                            context_type="global", horizon=7, status="pending"))
        s.commit()
        s.close()
        t0 = time.perf_counter()
        train_group(gid, ds, "revenue", "global", None, 7, ["rf"], sync_url)
        results["stages"]["e2e_rf_7d"] = round(time.perf_counter() - t0, 1)
        s = Session()
        s.delete(s.get(ForecastGroup, gid))  # cascades to runs + points
        s.commit()
        s.close()
        engine.dispose()

        results["counters"] = counters
        out = Path(args.out)
        if not out.is_absolute():
            out = BACKEND_DIR.parent / out  # repo root, e.g. docs/forecast-baseline.json
        out.write_text(json.dumps(results, indent=2))
        print(f"\nwrote {out}")
        print(json.dumps(results["stages"], indent=2))
        return 0
    finally:
        EST.build_frame = orig_frame
        EST.fit_predict = orig_fit_predict
        _R.fit_predict = orig_fit_predict


if __name__ == "__main__":
    raise SystemExit(main())
