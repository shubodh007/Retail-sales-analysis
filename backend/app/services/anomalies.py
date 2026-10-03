"""Anomaly detection: trailing median + MAD robust z-scores. No causation claims.

For each eligible daily series (global, every country, top products by
revenue with >= 90 points): baseline(t) = median of the previous 28 days
(trailing only — never centered, never future). deviation = 0.6745*(x -
median)/MAD, the robust z-score. Flagged when |z] >= 3.5. The first 28
points of a series are warm-up (no flags). Deterministic: no sampling,
no randomness, pandas only (series are mart-sized, not raw rows).
"""
import uuid

import pandas as pd
from sqlalchemy import text

from app.db.session import make_job_engine

METHOD = "trailing_median_mad_28"
WINDOW = 28
THRESHOLD = 3.5
MIN_POINTS = 90  # product/country eligibility; global always runs


def detect_points(dates: list, values: list[float]) -> list[dict]:
    """Pure function over one series. Unit-tested; knows nothing about DB."""
    s = pd.Series(values, dtype=float)
    med = s.shift(1).rolling(WINDOW, min_periods=WINDOW).median()
    mad = s.shift(1).rolling(WINDOW, min_periods=WINDOW).apply(
        lambda w: (w - w.median()).abs().median(), raw=False)
    out = []
    for i in range(len(s)):
        if pd.isna(med.iloc[i]):
            continue
        # Floor scaled MAD so perfectly flat baselines don't blind the
        # detector (zero MAD would skip every spike sitting on a flat run).
        floor = max(abs(med.iloc[i]) * 0.01, 1e-9)
        m = max(mad.iloc[i] or 0, floor)
        z = 0.6745 * (s.iloc[i] - med.iloc[i]) / m
        if abs(z) >= THRESHOLD:
            out.append({"date": dates[i], "observed": float(s.iloc[i]),
                        "expected": float(med.iloc[i]), "deviation": float(z)})
    return out


def _series(engine, dataset_id: uuid.UUID, table: str, key_col: str | None,
            key: str | None) -> pd.DataFrame:
    q = f"SELECT date, revenue FROM {table} WHERE dataset_id=:d"
    params: dict = {"d": str(dataset_id)}
    if key_col:
        q += f" AND {key_col}=:k"
        params["k"] = key
    q += " ORDER BY date"
    with engine.connect() as conn:
        return pd.read_sql(text(q), conn, params=params, parse_dates=["date"])


def build_anomalies(dataset_id: uuid.UUID, sync_url: str, top_products: int = 200,
                    source: str = "unknown") -> dict:
    from app.db.session import log_job_target

    # Temporary safe diagnostics immediately before the failing connection.
    log_job_target(source, sync_url, f"anomalies-{dataset_id}")
    engine = make_job_engine(sync_url, source=source)
    rows: list[dict] = []
    skipped_sparse = 0

    def harvest(dimension: str, key: str, df: pd.DataFrame):
        nonlocal skipped_sparse
        # Density gate: intermittent series (median <= 0) carry no stable
        # baseline; flagging them would manufacture noise as signal.
        if float(df["revenue"].median()) <= 0:
            skipped_sparse += 1
            return
        dates = [d.strftime("%Y-%m-%d") for d in df["date"]]
        for hit in detect_points(dates, list(df["revenue"])):
            rows.append({"dataset_id": str(dataset_id), "dimension": dimension,
                         "dim_key": key, "date": hit["date"], "observed": hit["observed"],
                         "expected": hit["expected"], "deviation": hit["deviation"],
                         "method": METHOD})

    g = _series(engine, dataset_id, "sales_daily", None, None)
    harvest("global", "", g)

    with engine.connect() as conn:
        countries = pd.read_sql(
            text("SELECT DISTINCT country FROM country_daily WHERE dataset_id=:d"),
            conn, params={"d": str(dataset_id)})["country"].tolist()
    for c in countries:
        df = _series(engine, dataset_id, "country_daily", "country", c)
        if len(df) >= MIN_POINTS:
            harvest("country", c, df)

    with engine.connect() as conn:
        prods = pd.read_sql(
            text("SELECT stockcode FROM product_summary WHERE dataset_id=:d"
                 " ORDER BY revenue DESC LIMIT :n"),
            conn, params={"d": str(dataset_id), "n": top_products})["stockcode"].tolist()
    for p in prods:
        df = _series(engine, dataset_id, "product_daily", "stockcode", p)
        if len(df) >= MIN_POINTS:
            harvest("product", p, df)

    import psycopg2
    from sqlalchemy.engine import make_url
    if ":***@" in sync_url:
        raise ValueError(
            f"refusing masked database URL from source={source}: password is '***'"
        )
    u = make_url(sync_url)
    if not u.username:
        raise ValueError(
            f"database URL from source={source} has no username: "
            "set DATABASE_URL with the Supabase pooler user postgres.<project>"
        )
    query = dict(u.query)
    kwargs: dict = {"host": u.host, "port": u.port or 5432,
                    "user": u.username,
                    "dbname": u.database, "connect_timeout": 10}
    if u.password:
        kwargs["password"] = u.password
    if "sslmode" in query:  # Supabase mandates TLS
        kwargs["sslmode"] = query["sslmode"]
    log_job_target(source, sync_url, f"anomalies-psycopg2-{dataset_id}")
    conn = psycopg2.connect(**kwargs)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM anomalies WHERE dataset_id=%s", (str(dataset_id),))
        for r in rows:
            cur.execute(
                "INSERT INTO anomalies (dataset_id, dimension, dim_key, date, observed,"
                " expected, deviation, method) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (r["dataset_id"], r["dimension"], r["dim_key"], r["date"], r["observed"],
                 r["expected"], r["deviation"], r["method"]))
    conn.close()
    return {"global": sum(1 for r in rows if r["dimension"] == "global"),
            "country": sum(1 for r in rows if r["dimension"] == "country"),
            "product": sum(1 for r in rows if r["dimension"] == "product"),
            "skipped_sparse": skipped_sparse}
