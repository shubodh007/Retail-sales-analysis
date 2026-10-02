"""Contextual daily-revenue series from marts. Global / product / country.

A context trains only with sufficient history: len >= max(60, 2*horizon).
Otherwise InsufficientHistory with an honest reason (surfaced as 422).
"""
import uuid

import pandas as pd
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_job_engine
from app.forecast.interface import InsufficientHistory


def _engine(sync_url: str | None = None):
    return make_job_engine(sync_url or get_settings().database_url)


def load_series(dataset_id: uuid.UUID, context_type: str, context_id: str | None,
                horizon: int, sync_url: str | None = None) -> pd.DataFrame:
    if context_type == "global":
        sql = ("SELECT date, revenue AS y FROM sales_daily WHERE dataset_id=:d ORDER BY date")
        params: dict = {"d": str(dataset_id)}
    elif context_type == "product":
        sql = ("SELECT date, revenue AS y FROM product_daily WHERE dataset_id=:d AND stockcode=:c"
               " ORDER BY date")
        params = {"d": str(dataset_id), "c": context_id}
    elif context_type == "country":
        sql = ("SELECT date, revenue AS y FROM country_daily WHERE dataset_id=:d AND country=:c"
               " ORDER BY date")
        params = {"d": str(dataset_id), "c": context_id}
    else:
        raise ValueError(f"unknown context: {context_type}")
    with _engine(sync_url).connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params, parse_dates=["date"])
    if df.empty:
        raise InsufficientHistory(f"no history for {context_type}={context_id}")
    df = df.sort_values("date").reset_index(drop=True)
    need = max(60, 2 * horizon)
    if len(df) < need:
        raise InsufficientHistory(
            f"only {len(df)} daily points for {context_type}={context_id or 'global'};"
            f" need >= {need} for a {horizon}-day horizon")
    df["date"] = pd.to_datetime(df["date"])
    return df


def expanding_folds(n: int, horizon: int, n_splits: int = 2) -> list[tuple[range, range]]:
    """Chronological folds: test blocks of `horizon` at the tail, train grows."""
    folds = []
    for k in range(n_splits, 0, -1):
        test_end = n - (k - 1) * horizon
        test_start = test_end - horizon
        if test_start < max(60, horizon):
            continue
        folds.append((range(0, test_start), range(test_start, test_end)))
    if not folds:
        test_start = n - horizon
        folds.append((range(0, test_start), range(test_start, n)))
    return folds
