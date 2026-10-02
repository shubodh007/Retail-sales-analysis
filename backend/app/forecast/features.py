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
