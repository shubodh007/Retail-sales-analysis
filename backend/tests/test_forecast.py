"""Forecasting tests: leakage, metrics, splits, schema, API lifecycle."""
import time
from pathlib import Path

import pandas as pd

from app.forecast import metrics as M
from app.forecast.estimators import fit_predict
from app.forecast.features import build_frame
from app.forecast.series import expanding_folds
from tests.conftest import upload_and_wait

SAMPLES = Path(__file__).resolve().parents[2] / "datasets" / "samples"


def _toy(n=120):
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    y = pd.Series([100 + 0.5 * i + 10 * (i % 7 == 5) for i in range(n)], dtype=float)
    return dates, y


def test_folds_are_chronological():
    folds = expanding_folds(604, 30)
    assert len(folds) == 2
    for tr, te in folds:
        assert max(tr) < min(te)  # train strictly before test
    assert list(folds[-1][1]) == list(range(574, 604))  # tail block
    assert list(folds[0][1]) == list(range(544, 574))


def test_folds_single_when_short():
    folds = expanding_folds(70, 30)
    assert len(folds) == 1
    tr, te = folds[0]
    assert max(tr) < min(te) and len(te) == 30


def test_lag_uses_past_only():
    dates, y = _toy()
    f = build_frame(dates, y)
    # frame drops first 28 rows; row i of frame == original index i+28
    row = f.iloc[10]
    assert row["lag_7"] == y.iloc[10 + 28 - 7]
    assert row["lag_28"] == y.iloc[10]


def test_rolling_excludes_current():
    dates = pd.date_range("2023-01-01", periods=60, freq="D")
    y = pd.Series([10.0] * 60)
    y.iloc[50] = 1000.0  # spike at t=50
    f = build_frame(dates, y)
    at_spike = f[f["y"] == 1000.0].iloc[0]
    # rolling window sees only the 7 values BEFORE the spike
    assert at_spike["roll_mean_7"] == 10.0
    # the spike enters the window only for later rows
    later = f.iloc[f[f["y"] == 1000.0].index[0] - f.index[0] + 1]
    assert later["roll_mean_7"] > 10.0


def test_no_future_leak_at_boundary():
    dates, y = _toy(100)
    full = build_frame(dates, y)
    prefix = build_frame(dates[:80], y[:80])
    # boundary row (original idx 79 == frame row 79-28) identical from full/prefix
    a = full.iloc[79 - 28].drop(["y", "date"]).astype(float)
    b = prefix.iloc[-1].drop(["y", "date"]).astype(float)
    pd.testing.assert_series_equal(a, b, check_names=False)


def test_zero_actuals_invalidate_mape():
    m, status = M.evaluate([0.0, 5.0, 10.0], [1.0, 5.0, 9.0])
    assert status == "unstable_zero_actuals"
    assert m["mape"] is None
    assert m["wape"] > 0 and m["wape"] < 100


def test_valid_mape_reported():
    m, status = M.evaluate([100.0, 200.0], [110.0, 190.0])
    assert status == "ok"
    assert abs(m["mape"] - 7.5) < 0.01


def test_rf_result_schema():
    dates, y = _toy(150)
    df = pd.DataFrame({"date": dates, "y": y})
    res = fit_predict("rf", df, 7)
    assert res.model == "rf" and res.horizon == 7
    assert len(res.fc_points) == 7 and len(res.fc_dates) == 7
    assert len(res.fc_lower) == 7 and len(res.fc_upper) == 7
    assert res.interval_type == "empirical_residual"
    assert len(res.val_actual) == 7 and len(res.val_predicted) == 7
    for k in ("mae", "rmse", "wape", "smape"):
        assert isinstance(res.metrics[k], float)
    assert res.train_from < res.train_to and res.val_from <= res.val_to


def test_horizon_validation(client, narrow_csv):
    did = upload_and_wait(client, narrow_csv, "n.csv")
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "horizon": 45, "models": ["rf"]})
    assert r.status_code == 422
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "horizon": 7, "models": ["nope"]})
    assert r.status_code == 422


def test_insufficient_history_fails_group(client, narrow_csv):
    did = upload_and_wait(client, narrow_csv, "n.csv")
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "context_type": "product",
                          "context_id": "A001", "horizon": 30, "models": ["rf"]})
    assert r.status_code == 202
    gid = r.json()["id"]
    for _ in range(60):
        g = client.get(f"/api/v1/forecasts/runs/{gid}").json()
        if g["status"] in ("done", "failed"):
            break
        time.sleep(5)
    assert g["status"] == "failed"
    assert "need >=" in (g["error"] or "")


def test_lifecycle_rf_on_synthetic(client):
    csv = SAMPLES / "retail_synthetic.csv"
    did = upload_and_wait(client, csv, "syn.csv")
    r = client.post("/api/v1/forecasts/runs",
                    json={"dataset_id": did, "horizon": 7, "models": ["rf"]})
    assert r.status_code == 202
    gid = r.json()["id"]
    g = {}
    for _ in range(120):
        g = client.get(f"/api/v1/forecasts/runs/{gid}").json()
        if g["status"] == "done":
            break
        assert g["status"] != "failed", g.get("error")
        time.sleep(5)
    assert g["status"] == "done", g.get("error")
    assert g["best_model"] == "rf"
    run = g["runs"][0]
    assert len(run["forecast"]) == 7
    assert len(run["validation"]) == 7
    assert len(run["history"]) > 60
    assert run["metrics"]["wape"] is not None

    cmp = client.get(f"/api/v1/forecasts/compare/{gid}").json()
    assert cmp["selection"]["best_model"] == "rf"
    assert cmp["selection"]["metric"] == "wape"
