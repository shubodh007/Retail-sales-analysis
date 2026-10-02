"""Analytical marts: Spark aggregation over curated Parquet, loaded to PG via JDBC.

Only file-backed Spark ops (see docs/java-spark-setup.md). Marts skipped
when the dataset lacks the dimension (capability-driven, never fabricated).
"""
import uuid
from urllib.parse import parse_qsl, urlparse

import psycopg2
from pyspark.sql import functions as F

from app.services.mapping import detect_invoice_column
from app.spark.session import get_spark


def _targets(sync_url: str):
    """Split a SQLAlchemy sync URL (postgresql+psycopg2://...) into JDBC URL + psycopg2 kwargs.

    Forwards ``sslmode`` (required by Supabase) to both transports.
    """
    u = urlparse("postgresql://" + sync_url.split("://", 1)[1])
    query = dict(parse_qsl(u.query))
    jdbc = f"jdbc:postgresql://{u.hostname}:{u.port or 5432}{u.path}"
    if "sslmode" in query:
        jdbc += f"?sslmode={query['sslmode']}"
    pg = {"host": u.hostname, "port": u.port or 5432, "user": u.username or "postgres",
          "dbname": u.path.lstrip("/"), "connect_timeout": 10}
    if u.password:
        pg["password"] = u.password
    if "sslmode" in query:
        pg["sslmode"] = query["sslmode"]
    return jdbc, pg


JDBC_PROPS = {
    "driver": "org.postgresql.Driver",
    # Send strings as UNKNOWN so PG infers UUID for dataset_id (Spark has no UUID type).
    "stringtype": "unspecified",
}


def _jdbc(df, table: str, jdbc_url: str, pg: dict) -> int:
    props = dict(JDBC_PROPS)
    props["user"] = pg["user"]
    if pg.get("password"):
        props["password"] = pg["password"]
    df.write.jdbc(jdbc_url, table, mode="append", properties=props)
    return df.count()


def _clear(dataset_id: uuid.UUID, tables: list[str], pg: dict) -> None:
    conn = psycopg2.connect(**pg)
    conn.autocommit = True
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"DELETE FROM {t} WHERE dataset_id = %s", (str(dataset_id),))
    conn.close()


def build_marts(dataset_id: uuid.UUID, parquet_path: str, schema_map: dict[str, str],
                sync_url: str) -> dict:
    jdbc_url, pg = _targets(sync_url)
    spark = get_spark()
    df = spark.read.parquet(parquet_path)
    inv = detect_invoice_column(df.columns)
    day = F.to_date("date")

    has_geo = "region" in schema_map
    has_cust = "customer_id" in schema_map
    has_desc = "__desc" in df.columns
    desc = F.first("__desc") if has_desc else F.lit("")

    tables = ["sales_daily", "sales_monthly", "product_daily", "product_summary"]
    if has_geo:
        tables.append("country_daily")
    if has_cust:
        tables.append("customer_summary")
    _clear(dataset_id, tables, pg)

    did = F.lit(str(dataset_id)).cast("string")
    counts: dict[str, int] = {}

    daily = df.groupBy(day.alias("d")).agg(
        F.countDistinct(inv).alias("orders"),
        F.sum("__qty").alias("qty"), F.sum("revenue").alias("revenue"))
    counts["sales_daily"] = _jdbc(
        daily.select(did.alias("dataset_id"), F.col("d").alias("date"), "orders", "qty", "revenue"),
        "sales_daily", jdbc_url, pg)

    monthly = df.groupBy(F.date_trunc("month", "date").cast("date").alias("m")).agg(
        F.countDistinct(inv).alias("orders"),
        F.sum("__qty").alias("qty"), F.sum("revenue").alias("revenue"))
    counts["sales_monthly"] = _jdbc(
        monthly.select(did.alias("dataset_id"), F.col("m").alias("month"), "orders", "qty", "revenue"),
        "sales_monthly", jdbc_url, pg)

    pday = df.groupBy(day.alias("d"), "__prod").agg(
        desc.alias("description"), F.sum("__qty").alias("qty"),
        F.sum("revenue").alias("revenue"), F.countDistinct(inv).alias("orders"))
    counts["product_daily"] = _jdbc(
        pday.select(did.alias("dataset_id"), F.col("d").alias("date"),
                    F.col("__prod").alias("stockcode"), "description", "qty", "revenue", "orders"),
        "product_daily", jdbc_url, pg)

    psum = df.groupBy("__prod").agg(
        desc.alias("description"), F.sum("__qty").alias("qty"),
        F.sum("revenue").alias("revenue"), F.countDistinct(inv).alias("orders"),
        F.min(day).alias("first_date"), F.max(day).alias("last_date"))
    counts["product_summary"] = _jdbc(
        psum.select(did.alias("dataset_id"), F.col("__prod").alias("stockcode"), "description",
                    "qty", "revenue", "orders", "first_date", "last_date"),
        "product_summary", jdbc_url, pg)

    if has_geo:
        cday = df.filter(F.col("__country").isNotNull() & (F.col("__country") != "")).groupBy(
            day.alias("d"), "__country").agg(
            F.sum("__qty").alias("qty"), F.sum("revenue").alias("revenue"),
            F.countDistinct(inv).alias("orders"))
        counts["country_daily"] = _jdbc(
            cday.select(did.alias("dataset_id"), F.col("d").alias("date"),
                        F.col("__country").alias("country"), "qty", "revenue", "orders"),
            "country_daily", jdbc_url, pg)

    if has_cust:
        cust = df.filter(F.col("__cust").isNotNull() & (F.col("__cust") != ""))
        csum = cust.groupBy("__cust").agg(
            F.first("__country").alias("country"), F.countDistinct(inv).alias("orders"),
            F.sum("__qty").alias("qty"), F.sum("revenue").alias("revenue"),
            F.min(day).alias("first_date"), F.max(day).alias("last_date"))
        counts["customer_summary"] = _jdbc(
            csum.select(did.alias("dataset_id"), F.col("__cust").alias("customer_id"), "country",
                        "orders", "qty", "revenue", "first_date", "last_date"),
            "customer_summary", jdbc_url, pg)

    return counts
