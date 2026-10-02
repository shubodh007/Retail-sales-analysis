"""Async forecast jobs. POST returns a group id immediately; training runs in a
BackgroundTasks worker thread and persists progress to forecast_* tables."""
import time
import uuid

from sqlalchemy.orm import sessionmaker

from app.db.session import make_job_engine
from app.forecast.estimators import fit_predict
from app.forecast.interface import InsufficientHistory
from app.models.forecast import ForecastGroup, ForecastPoint, ForecastRun


def _sync_session(sync_url: str):
    engine = make_job_engine(sync_url)
    return sessionmaker(engine, expire_on_commit=False)


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
        results = {}
        for name in models:
            run = ForecastRun(group_id=group_id, model=name, status="running")
            session.add(run)
            session.commit()
            t0 = time.time()
            try:
                res = fit_predict(name, df, horizon)
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
                results[name] = res
            except Exception as e:
                # Type + message only: full tracebacks would leak paths via the API.
                run.status = "failed"
                run.error = f"{type(e).__name__}: {e}"
                run.duration_s = time.time() - t0
                session.commit()
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
