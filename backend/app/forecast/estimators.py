"""Four models, one architecture: fit on expanding folds, evaluate, refit full.

Intervals: ARIMA/Prophet analytic; RF/XGBoost empirical residual bands from
out-of-fold residuals (documented as prediction intervals, not analytic CIs).
"""
import time

import numpy as np
import pandas as pd

from app.forecast import metrics as M
from app.forecast.features import FEATURE_COLS, build_frame
from app.forecast.interface import ForecastResult
from app.forecast.series import expanding_folds

MODELS = ("arima", "prophet", "rf", "xgb")


def _avg_metrics(fold_metrics: list[dict]) -> tuple[dict, str]:
    out: dict = {}
    for k in ("mae", "rmse", "wape", "smape"):
        out[k] = float(np.mean([m[k] for m in fold_metrics]))
    mapes = [m["mape"] for m in fold_metrics if m["mape"] is not None]
    out["mape"] = float(np.mean(mapes)) if len(mapes) == len(fold_metrics) else None
    status = "ok" if out["mape"] is not None else "unstable_zero_actuals"
    return out, status


def _residual_band(residuals: list[float]) -> tuple[float, float]:
    lo, hi = float(np.quantile(residuals, 0.10)), float(np.quantile(residuals, 0.90))
    return lo, hi


def _future_dates(last: pd.Timestamp, horizon: int) -> list[str]:
    return [(last + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(horizon)]


def _fit_arima(y: pd.Series, horizon: int):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    tried = []
    for order, seasonal in [((1, 1, 1), (1, 1, 1, 7)), ((2, 1, 2), None), ((1, 1, 1), None)]:
        try:
            kw = {"seasonal_order": seasonal} if seasonal else {}
            res = SARIMAX(y, order=order, enforce_stationarity=False,
                          enforce_invertibility=False, **kw).fit(disp=False)
            return res, {"order": order, "seasonal_order": seasonal}
        except Exception as e:
            tried.append(str(type(e).__name__))
    raise RuntimeError(f"ARIMA failed orders tried={tried}")


def _run_arima(df: pd.DataFrame, horizon: int) -> ForecastResult:
    t0 = time.time()
    folds = expanding_folds(len(df), horizon)
    y = df["y"]
    fms, residuals = [], []
    for tr, te in folds:
        res, _ = _fit_arima(y.iloc[list(tr)], horizon)
        pred = list(res.get_forecast(steps=len(te)).predicted_mean)
        actual = list(y.iloc[list(te)])
        m, _ = M.evaluate(actual, pred)
        fms.append(m)
        residuals += [a - p for a, p in zip(actual, pred)]
    res, cfg = _fit_arima(y, horizon)
    fc = res.get_forecast(steps=horizon)
    ci = fc.conf_int(alpha=0.05)
    avg, status = _avg_metrics(fms)
    r = ForecastResult(model="arima", horizon=horizon, metrics=avg, mape_status=status,
                       interval_type="analytic",
                       config={**cfg, "interval": "analytic_95", "folds": len(folds)},
                       duration_s=time.time() - t0)
    r.val_dates = [d.strftime("%Y-%m-%d") for d in df["date"].iloc[list(folds[-1][1])]]
    last_fold = folds[-1]
    r.val_actual = list(y.iloc[list(last_fold[1])])
    rr, _ = _fit_arima(y.iloc[list(last_fold[0])], horizon)
    r.val_predicted = list(rr.get_forecast(steps=len(last_fold[1])).predicted_mean)
    r.fc_dates = _future_dates(df["date"].iloc[-1], horizon)
    r.fc_points = [float(v) for v in fc.predicted_mean]
    r.fc_lower = [float(v) for v in ci.iloc[:, 0]]
    r.fc_upper = [float(v) for v in ci.iloc[:, 1]]
    r.train_from = df["date"].iloc[0].strftime("%Y-%m-%d")
    r.train_to = df["date"].iloc[-1].strftime("%Y-%m-%d")
    r.val_from, r.val_to = r.val_dates[0], r.val_dates[-1]
    return r


def _run_prophet(df: pd.DataFrame, horizon: int) -> ForecastResult:
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    from prophet import Prophet

    t0 = time.time()
    folds = expanding_folds(len(df), horizon)
    fms, residuals = [], []

    def _fit(sub: pd.DataFrame):
        m = Prophet(weekly_seasonality=True, yearly_seasonality=True,
                    daily_seasonality=False, interval_width=0.9)
        m.fit(sub.rename(columns={"date": "ds", "y": "y"})[["ds", "y"]])
        return m

    for tr, te in folds:
        m = _fit(df.iloc[list(tr)])
        fut = m.make_future_dataframe(periods=len(te), freq="D", include_history=False)
        pred = list(m.predict(fut)["yhat"])
        actual = list(df["y"].iloc[list(te)])
        mm, _ = M.evaluate(actual, pred)
        fms.append(mm)
        residuals += [a - p for a, p in zip(actual, pred)]
    m = _fit(df)
    fut = m.make_future_dataframe(periods=horizon, freq="D", include_history=False)
    fc = m.predict(fut)
    avg, status = _avg_metrics(fms)
    r = ForecastResult(model="prophet", horizon=horizon, metrics=avg, mape_status=status,
                       interval_type="analytic",
                       config={"interval": "uncertainty_90", "folds": len(folds)},
                       duration_s=time.time() - t0)
    last_fold = folds[-1]
    r.val_dates = [d.strftime("%Y-%m-%d") for d in df["date"].iloc[list(last_fold[1])]]
    r.val_actual = list(df["y"].iloc[list(last_fold[1])])
    mm = _fit(df.iloc[list(last_fold[0])])
    fut2 = mm.make_future_dataframe(periods=len(last_fold[1]), freq="D", include_history=False)
    r.val_predicted = list(mm.predict(fut2)["yhat"])
    r.fc_dates = [d.strftime("%Y-%m-%d") for d in fc["ds"]]
    r.fc_points = [float(v) for v in fc["yhat"]]
    r.fc_lower = [float(v) for v in fc["yhat_lower"]]
    r.fc_upper = [float(v) for v in fc["yhat_upper"]]
    r.train_from = df["date"].iloc[0].strftime("%Y-%m-%d")
    r.train_to = df["date"].iloc[-1].strftime("%Y-%m-%d")
    r.val_from, r.val_to = r.val_dates[0], r.val_dates[-1]
    return r


def _recursive_predict(model, hist: pd.DataFrame, horizon: int) -> list[float]:
    """Step forward using only past actuals + own predictions (no future leak).

    Each step appends its prediction to the history first, so lags and
    rolling windows for step t+1 see actuals plus predictions up to t.
    The placeholder value for the not-yet-predicted point is never read by
    its own feature row (every feature looks back >= 1 step).
    """
    extended_y = list(hist["y"].astype(float))
    extended_d = list(pd.to_datetime(hist["date"]))
    out = []
    for _ in range(horizon):
        extended_d.append(extended_d[-1] + pd.Timedelta(days=1))
        extended_y.append(extended_y[-1])  # placeholder, never read by its own row
        frame = build_frame(pd.Series(extended_d), pd.Series(extended_y))
        pred = float(model.predict(frame[FEATURE_COLS].iloc[[-1]])[0])
        out.append(pred)
        extended_y[-1] = pred  # prediction feeds subsequent steps
    return out


def _run_ml(df: pd.DataFrame, horizon: int, kind: str) -> ForecastResult:
    t0 = time.time()
    frame = build_frame(df["date"], df["y"])
    # map frame rows back to original positions: frame drops first 28 rows
    offset = len(df) - len(frame)
    folds = expanding_folds(len(df), horizon)
    fms, residuals = [], []

    def _fit(fr: pd.DataFrame):
        X, y = fr[FEATURE_COLS], fr["y"]
        if kind == "rf":
            from sklearn.ensemble import RandomForestRegressor
            m = RandomForestRegressor(n_estimators=200, min_samples_leaf=5,
                                      n_jobs=-1, random_state=42)
        else:
            from xgboost import XGBRegressor
            m = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8,
                             n_jobs=-1, random_state=42)
        m.fit(X, y)
        return m

    for tr, te in folds:
        tri = [i - offset for i in tr if i - offset >= 0]
        sub = frame.iloc[tri]
        m = _fit(sub)
        hist = df.iloc[list(tr)][["date", "y"]]
        pred = _recursive_predict(m, hist, len(te))
        actual = list(df["y"].iloc[list(te)])
        mm, _ = M.evaluate(actual, pred)
        fms.append(mm)
        residuals += [a - p for a, p in zip(actual, pred)]
    m = _fit(frame)
    preds = _recursive_predict(m, df[["date", "y"]], horizon)
    lo, hi = _residual_band(residuals)
    avg, status = _avg_metrics(fms)
    cfg = {"features": FEATURE_COLS, "folds": len(folds),
           "interval": "empirical_residual_p10_p90",
           "n_estimators": 200 if kind == "rf" else 300, "random_state": 42}
    r = ForecastResult(model="rf" if kind == "rf" else "xgb", horizon=horizon,
                       metrics=avg, mape_status=status, interval_type="empirical_residual",
                       config=cfg, duration_s=time.time() - t0)
    last_fold = folds[-1]
    r.val_dates = [d.strftime("%Y-%m-%d") for d in df["date"].iloc[list(last_fold[1])]]
    r.val_actual = list(df["y"].iloc[list(last_fold[1])])
    tri = [i - offset for i in last_fold[0] if i - offset >= 0]
    mm = _fit(frame.iloc[tri])
    r.val_predicted = _recursive_predict(mm, df.iloc[list(last_fold[0])][["date", "y"]],
                                         len(last_fold[1]))
    r.fc_dates = _future_dates(df["date"].iloc[-1], horizon)
    r.fc_points = preds
    r.fc_lower = [p + lo for p in preds]
    r.fc_upper = [p + hi for p in preds]
    r.train_from = df["date"].iloc[0].strftime("%Y-%m-%d")
    r.train_to = df["date"].iloc[-1].strftime("%Y-%m-%d")
    r.val_from, r.val_to = r.val_dates[0], r.val_dates[-1]
    return r


def fit_predict(model: str, df: pd.DataFrame, horizon: int) -> ForecastResult:
    if model == "arima":
        return _run_arima(df, horizon)
    if model == "prophet":
        return _run_prophet(df, horizon)
    if model in ("rf", "xgb"):
        return _run_ml(df, horizon, model)
    raise ValueError(f"unknown model: {model}")
