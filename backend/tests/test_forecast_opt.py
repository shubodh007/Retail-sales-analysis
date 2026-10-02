"""Optimization regression tests: incremental recursion equivalence,
result-cache reuse, in-flight dedupe, dataset isolation.

The legacy full-rebuild recursion below is a TEST-ONLY reference mirroring
the pre-optimization implementation; production code must match it.
"""
import uuid
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.api.forecasts as fc_api
from app.core import jobs
from app.forecast.estimators import _recursive_predict
from app.forecast.features import FEATURE_COLS, build_frame, next_feature_row
from app.models.dataset import Dataset
from app.models.forecast import ForecastGroup, ForecastRun
from tests.conftest import TEST_SYNC_URL, upload_and_wait


def _toy(n=150):
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    y = pd.Series([100 + 0.5 * i + 10 * (i % 7 == 5) for i in range(n)], dtype=float)
    return dates, y


def _legacy_recursive_predict(model, hist: pd.DataFrame, horizon: int) -> list[float]:
    """Pre-optimization reference: full frame rebuild per timestep."""
    extended_y = list(hist["y"].astype(float))
    extended_d = list(pd.to_datetime(hist["date"]))
    out = []
    for _ in range(horizon):
        extended_d.append(extended_d[-1] + pd.Timedelta(days=1))
        extended_y.append(extended_y[-1])
        frame = build_frame(pd.Series(extended_d), pd.Series(extended_y))
        pred = float(model.predict(frame[FEATURE_COLS].iloc[[-1]])[0])
        out.append(pred)
        extended_y[-1] = pred
    return out


def test_next_feature_row_matches_full_frame():
    dates, y = _toy()
    ey, ed, placeholders = list(y), list(dates), []
    legacy_rows = []
    for _ in range(10):
        ed.append(ed[-1] + pd.Timedelta(days=1))
        ey.append(ey[-1])
        placeholders.append(ey[-1])
        f = build_frame(pd.Series(ed), pd.Series(ey))
        legacy_rows.append(dict(zip(FEATURE_COLS, f[FEATURE_COLS].iloc[-1])))
    ey2 = list(y)
    for step in range(10):
        nxt = dates[-1] + pd.Timedelta(days=step + 1)
        row = next_feature_row(ey2, nxt, len(ey2))
        for k in FEATURE_COLS:
            tol = 1e-6 if k.startswith("roll_std") else 0.0
            # roll_std may differ in the last ulp: pandas accumulates rounding
            # over the full series vs the trailing slice (values ~1e-9 relative).
            assert abs(float(row[k]) - float(legacy_rows[step][k])) <= tol, k
        ey2.append(placeholders[step])


def test_recursive_predict_matches_legacy():
    from sklearn.ensemble import RandomForestRegressor

    dates, y = _toy()
    hist = pd.DataFrame({"date": dates, "y": y})
    fr = build_frame(dates, y)
    m = RandomForestRegressor(n_estimators=50, min_samples_leaf=5,
                              n_jobs=1, random_state=42)
    m.fit(fr[FEATURE_COLS], fr["y"])
    new = _recursive_predict(m, hist, 30)
    old = _legacy_recursive_predict(m, hist, 30)
    assert len(new) == 30 == len(old)
    assert new == old  # tree splits do not flip at 1e-9 feature noise


def _sync_session():
    engine = create_engine(TEST_SYNC_URL)
    return sessionmaker(engine, expire_on_commit=False), engine


def _seed_done_group(dataset_id: str, horizon: int, models=("rf",)):
    Session, engine = _sync_session()
    s = Session()
    gid = uuid.uuid4()
    s.add(ForecastGroup(id=gid, dataset_id=uuid.UUID(dataset_id), target="revenue",
                         context_type="global", horizon=horizon, status="done",
                         best_model=models[0]))
    for name in models:
        s.add(ForecastRun(group_id=gid, model=name, status="done",
                           metrics={"wape": 10.0, "mae": 1.0, "rmse": 1.0,
                                    "smape": 5.0, "mape": None}))
    s.commit()
    s.close()
    engine.dispose()
    return gid


def _seed_pending_group(dataset_id: str, horizon: int):
    Session, engine = _sync_session()
    s = Session()
    gid = uuid.uuid4()
    s.add(ForecastGroup(id=gid, dataset_id=uuid.UUID(dataset_id), target="revenue",
                         context_type="global", horizon=horizon, status="running"))
    s.commit()
    s.close()
    engine.dispose()
    return gid


def _group_count(dataset_id: str) -> int:
    Session, engine = _sync_session()
    s = Session()
    n = len(s.execute(select(ForecastGroup).where(
        ForecastGroup.dataset_id == uuid.UUID(dataset_id))).scalars().all())
    s.close()
    engine.dispose()
    return n


def test_cache_reuses_completed_forecast(client, mini_csv):
    did = upload_and_wait(client, mini_csv, "cache.csv")
    gid = _seed_done_group(did, 7)
    before = _group_count(did)
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "horizon": 7, "models": ["rf"]})
    assert r.status_code == 202
    body = r.json()
    assert body["id"] == str(gid)
    assert body["status"] == "done" and body["cached"] is True
    assert _group_count(did) == before  # no retraining happened


def test_dedupe_returns_inflight_group(client, mini_csv):
    did = upload_and_wait(client, mini_csv, "dedupe.csv")
    gid = _seed_pending_group(did, 30)
    before = _group_count(did)
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "horizon": 30, "models": ["rf"]})
    assert r.status_code == 202
    body = r.json()
    assert body["id"] == str(gid) and body["status"] == "running"
    assert body["cached"] is False
    assert _group_count(did) == before


def test_cache_is_dataset_isolated(client, mini_csv, narrow_csv):
    did_a = upload_and_wait(client, mini_csv, "iso_a.csv")
    did_b = upload_and_wait(client, narrow_csv, "iso_b.csv")
    _seed_done_group(did_a, 7)
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did_b, "horizon": 7, "models": ["rf"]})
    assert r.status_code == 202
    body = r.json()
    assert body["cached"] is False  # dataset B must train, never reuse A's result
    # narrow.csv has 2 points -> insufficient history -> new group fails fast
    assert body["status"] in ("pending", "failed")


def test_forecast_rejects_unready_dataset(client, mini_csv):
    Session, engine = _sync_session()
    s = Session()
    did = uuid.uuid4()
    s.add(Dataset(id=did, filename="ghost.csv", status="processing",
                  row_count=0, schema_map={}, profile={}, parquet_path=""))
    s.commit()
    s.close()
    engine.dispose()
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": str(did), "horizon": 7})
    assert r.status_code == 422


def _pending_key_kwargs(dataset_id: str, horizon: int = 7):
    return {"dataset_id": uuid.UUID(dataset_id), "target": "revenue",
            "context_type": "global", "context_id": None, "horizon": horizon}


def test_inflight_unique_index_rejects_duplicates(client, mini_csv):
    """DB-level guard: two pending groups for one key cannot coexist."""
    did = upload_and_wait(client, mini_csv, "constraint.csv")
    Session, engine = _sync_session()
    s = Session()
    s.add(ForecastGroup(id=uuid.uuid4(), status="pending", **_pending_key_kwargs(did)))
    s.commit()
    s.add(ForecastGroup(id=uuid.uuid4(), status="pending", **_pending_key_kwargs(did)))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    n = len(s.execute(select(ForecastGroup).where(
        ForecastGroup.dataset_id == uuid.UUID(did))).scalars().all())
    assert n == 1
    s.close()
    engine.dispose()


def test_race_fallback_attaches_to_winner(client, mini_csv):
    """Simulated SELECT-then-INSERT race: pre-check misses, INSERT loses,
    request attaches to the winner instead of training twice."""
    did = upload_and_wait(client, mini_csv, "race.csv")
    winner = _seed_pending_group(did, 7)
    before = _group_count(did)
    real_find = fc_api._find_inflight
    calls = []

    async def flaky_find(session, req):
        calls.append(1)
        if len(calls) == 1:
            return None  # raced: winner committed after our SELECT
        return await real_find(session, req)

    with patch.object(fc_api, "_find_inflight", flaky_find):
        r = client.post("/api/v1/forecasts/runs",
                        json={"dataset_id": did, "horizon": 7, "models": ["rf"]})
    assert r.status_code == 202
    body = r.json()
    assert body["id"] == str(winner) and body["cached"] is False
    assert _group_count(did) == before  # loser inserted nothing


def test_insert_failure_releases_slot(client, mini_csv):
    """A failed group INSERT must not leak a job slot (else capacity
    drains permanently — MAX_CONCURRENT_JOBS is tiny)."""
    did = upload_and_wait(client, mini_csv, "slot.csv")
    boom = IntegrityError("INSERT INTO forecast_groups ...", {}, Exception("dup"))
    with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=boom):
        r = client.post("/api/v1/forecasts/runs",
                        json={"dataset_id": did, "horizon": 7, "models": ["rf"]})
    assert r.status_code == 409
    # Both slots acquirable => the failed request released its slot.
    s1 = jobs.acquire_or_429()
    try:
        s2 = jobs.acquire_or_429()
        s2.__exit__(None, None, None)
    finally:
        s1.__exit__(None, None, None)
