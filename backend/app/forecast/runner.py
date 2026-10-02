"""Async forecast jobs. POST returns a group id immediately; training runs in a
BackgroundTasks worker thread and persists progress to forecast_* tables.

One code path trains a single model (`_train_single_model`), used both
sequentially (default) and across a bounded thread pool
(`FORECAST_MAX_WORKERS`). Each model owns a short-lived session from a
NullPool engine; the group row is updated by the main thread only.
The final full-history fit stays separate from validation fits (no leakage).
"""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.session import make_job_engine
from app.forecast.estimators import fit_predict
from app.forecast.interface import InsufficientHistory
from app.models.forecast import ForecastGroup, ForecastPoint, ForecastRun


def _sync_session(sync_url: str):
    engine = make_job_engine(sync_url)
    return sessionmaker(engine, expire_on_commit=False)


def _train_single_model(group_id: uuid.UUID, model: str, df, hist: list[dict],
                        horizon: int, n_jobs: int, sync_url: str):
    """Train one model end-to-end (own session). Returns the ForecastResult."""
    Session = _sync_session(sync_url)
    session = Session()
    try:
        run = ForecastRun(group_id=group_id, model=model, status="running")
        session.add(run)
        session.commit()
        t0 = time.time()
        try:
            res = fit_predict(model, df, horizon, n_jobs=n_jobs)
            run.status = "done"
            run.metrics = dict(res.metrics)
            run.mape_status = res.mape_status
            run.interval_type = res.interval_type
            run.config = dict(res.config)
            run.train_from, run.train_to = res.train_from, res.train_to
            run.val_from, run.val_to = res.val_from, res.val_to
            run.duration_s = res.duration_s
            session.commit()
            pts = [ForecastPoint(run_id=run.id, date=h["date"], kind="history",
                                 actual=h["actual"], predicted=None, lower=None, upper=None)
                   for h in hist]
            pts += [ForecastPoint(run_id=run.id, date=d, kind="validation",
                                  actual=a, predicted=p, lower=None, upper=None)
                    for d, a, p in zip(res.val_dates, res.val_actual, res.val_predicted)]
            pts += [ForecastPoint(run_id=run.id, date=d, kind="forecast",
                                  actual=None, predicted=p, lower=lo, upper=hi)
                    for d, p, lo, hi in zip(res.fc_dates, res.fc_points,
                                            res.fc_lower, res.fc_upper)]
            session.add_all(pts)
            session.commit()
            return res
        except Exception as e:
            # Type + message only: full tracebacks would leak paths via the API.
            run.status = "failed"
            run.error = f"{type(e).__name__}: {e}"
            run.duration_s = time.time() - t0
            session.commit()
            return None
    finally:
        session.close()


def train_group(group_id: uuid.UUID, dataset_id: uuid.UUID, target: str,
                context_type: str, context_id: str | None, horizon: int,
                models: list[str], sync_url: str) -> None:
    from app.forecast.series import load_series

    Session = _sync_session(sync_url)
    session = Session()
    try:
        group = session.get(ForecastGroup, group_id)
        group.status = "running"
        session.commit()
        try:
            df = load_series(dataset_id, context_type, context_id, horizon, sync_url)
        except InsufficientHistory as e:
            group.status = "failed"
            group.error = str(e)
            session.commit()
            return
        hist = [{"date": d.strftime("%Y-%m-%d"), "actual": float(y)}
                for d, y in zip(df["date"], df["y"])]
    finally:
        session.close()

    workers = max(1, min(get_settings().forecast_max_workers, len(models)))
    # Parallel models each keep single-threaded learners so total CPU stays
    # bounded; sequential keeps the previous all-cores-per-model behavior.
    # ARIMA/Prophet/RF are bit-identical under both; XGB may shift ~0.3pp
    # WAPE (parallel histogram reduction) — measured, selection unaffected.
    n_jobs = 1 if workers > 1 else -1
    results: dict = {}
    if workers == 1:
        for name in models:
            res = _train_single_model(group_id, name, df, hist, horizon, n_jobs, sync_url)
            if res is not None:
                results[name] = res
    else:
        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="forecast") as pool:
            futs = {pool.submit(_train_single_model, group_id, name, df, hist,
                                horizon, n_jobs, sync_url): name for name in models}
            for fut in futs:
                res = fut.result()
                if res is not None:
                    results[futs[fut]] = res

    session = Session()
    try:
        group = session.get(ForecastGroup, group_id)
        done = {k: v for k, v in results.items() if v.metrics.get("wape") is not None}
        if done:
            best = min(done, key=lambda k: done[k].metrics["wape"])
            group.best_model = best
        group.status = "done" if done else "failed"
        if not done:
            group.error = "all models failed"
        session.commit()
    finally:
        session.close()
