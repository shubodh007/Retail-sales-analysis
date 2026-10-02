"""Leakage-safe supervised features. Every feature at time t uses only
information strictly before t: lags are shifted, rolling stats sit on the
lag-1 series, calendar parts come from the timestamp itself.
"""
import pandas as pd

LAGS = (1, 7, 14, 28)
ROLLING = (7, 14, 30)


def build_frame(dates: pd.Series, y: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"date": pd.to_datetime(dates), "y": y.astype(float).reset_index(drop=True)})
    for lag in LAGS:
        df[f"lag_{lag}"] = df["y"].shift(lag)
    lag1 = df["y"].shift(1)
    for w in ROLLING:
        df[f"roll_mean_{w}"] = lag1.rolling(w, min_periods=1).mean()
        df[f"roll_std_{w}"] = lag1.rolling(w, min_periods=1).std().fillna(0.0)
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    df["trend"] = range(len(df))
    return df.dropna().reset_index(drop=True)


FEATURE_COLS = ([f"lag_{l}" for l in LAGS]
                + [f"roll_mean_{w}" for w in ROLLING]
                + [f"roll_std_{w}" for w in ROLLING]
                + ["dow", "month", "is_weekend", "trend"])


def next_feature_row(hist: list[float], date, trend_idx: int) -> dict:
    """Single feature row for the timestep right after ``hist``.

    Matches the last row ``build_frame(dates, y)`` would produce for the
    same history: lags, rolling means, calendar parts and trend are
    bit-identical; ``roll_std_*`` may differ by <= 1e-6 because pandas
    accumulates float rounding over the full series vs the trailing slice
    (verified: never flips a tree split — see tests/test_forecast_opt.py).
    ``hist`` must hold >= max(LAGS) values (guaranteed: series gate is 60+).
    """
    n = len(hist)
    row: dict = {f"lag_{lag}": float(hist[n - lag]) for lag in LAGS}
    for w in ROLLING:
        tail = pd.Series(hist[max(0, n - w):], dtype=float)
        row[f"roll_mean_{w}"] = float(tail.rolling(w, min_periods=1).mean().iloc[-1])
        row[f"roll_std_{w}"] = float(
            tail.rolling(w, min_periods=1).std().fillna(0.0).iloc[-1])
    ts = pd.to_datetime(date)
    dow = int(ts.dayofweek)
    row["dow"] = dow
    row["month"] = int(ts.month)
    row["is_weekend"] = int(dow >= 5)
    row["trend"] = int(trend_idx)
    return row
