"""Dataset cleaning + profiling with PySpark. See docs/data-quality-policy.md.

JVM-native file reads only (no createDataFrame-from-rows, no Python UDFs).
Reconciliation: raw = duplicates + quarantined + cancellations + accepted.
"""
from datetime import datetime
from pathlib import Path

from pyspark.sql import functions as F

from app.spark.session import get_spark

DATE_FORMATS = ("yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm", "yyyy-MM-dd", "MM/dd/yyyy HH:mm",
                "MM/dd/yyyy", "dd/MM/yyyy HH:mm", "dd/MM/yyyy", "dd-MM-yyyy")


def _parse_date(col):
    return F.coalesce(*[F.to_timestamp(col, f) for f in DATE_FORMATS])


def profile_csv(csv_path: str, mapping: dict[str, str], parquet_path: str) -> dict:
    spark = get_spark()
    raw = spark.read.csv(csv_path, header=True, inferSchema=False)
    total = raw.count()
    deduped = raw.dropDuplicates()
    duplicates = total - deduped.count()

    date_col = mapping["date"]
    qty_col = mapping.get("quantity")
    price_col = mapping.get("unit_price")
    prod_col = mapping["product_id"]
    inv_col = next((c for r, c in mapping.items() if r in ("invoice_no", "invoice")), None)
    if inv_col is None:
        inv_col = next((c for c in raw.columns if c.lower().replace("_", "") in ("invoiceno", "invoice")), raw.columns[0])

    df = deduped.withColumn("__date", _parse_date(F.col(date_col)))
    ok_date = df.filter(F.col("__date").isNotNull())
    bad_date = total - duplicates - ok_date.count()

    df2 = ok_date.withColumn("__prod", F.trim(F.col(prod_col)))
    ok_prod = df2.filter(F.col("__prod").isNotNull() & (F.col("__prod") != ""))
    missing_product = ok_date.count() - ok_prod.count()

    df3 = ok_prod
    quarantine_reasons: dict[str, int] = {"bad_date": bad_date, "missing_product": missing_product}
    if qty_col:
        df3 = df3.withColumn("__qty", F.col(qty_col).cast("int"))
        bad_qty = df3.filter(F.col("__qty").isNull()).count()
        quarantine_reasons["bad_quantity"] = bad_qty
        df3 = df3.filter(F.col("__qty").isNotNull())
    else:
        df3 = df3.withColumn("__qty", F.lit(1))
    if price_col:
        df3 = df3.withColumn("__price", F.col(price_col).cast("double"))
        bad_price = df3.filter(F.col("__price").isNull() | (F.col("__price") <= 0)).count()
        quarantine_reasons["bad_price"] = bad_price
        df3 = df3.filter(F.col("__price").isNotNull() & (F.col("__price") > 0))
    else:
        df3 = df3.withColumn("__price", F.lit(0.0))

    is_cancel = F.upper(F.col(inv_col)).startswith("C") | (F.col("__qty") < 0)
    cancels = df3.filter(is_cancel)
    cancel_count = cancels.count()
    cancel_abs_revenue = cancels.agg(
        F.sum(F.abs(F.col("__qty")) * F.col("__price")).alias("v")).first()["v"] or 0.0
    accepted = df3.filter(~is_cancel)

    curated = accepted.withColumn("date", F.col("__date")).withColumn(
        "revenue", F.col("__qty").cast("double") * F.col("__price"))
    if "customer_id" in mapping:
        curated = curated.withColumn("__cust", F.trim(F.col(mapping["customer_id"])))
    if "region" in mapping:
        curated = curated.withColumn("__country", F.trim(F.col(mapping["region"])))
    if "product_name" in mapping:
        curated = curated.withColumn("__desc", F.trim(F.col(mapping["product_name"])))
    if "category" in mapping:
        curated = curated.withColumn("__cat", F.trim(F.col(mapping["category"])))
    curated.write.mode("overwrite").parquet(parquet_path)
    cancels.write.mode("overwrite").parquet(str(Path(parquet_path).parent / (Path(parquet_path).name + "__cancel")))

    # Bounds as UTC strings (never Python datetimes — OS-zone shift trap).
    bounds = curated.agg(
        F.date_format(F.min("date"), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("lo"),
        F.date_format(F.max("date"), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("hi"),
    ).first()
    date_from, date_to = bounds["lo"], bounds["hi"]

    null_pct = {}
    for c in raw.columns:
        n = raw.filter(F.col(c).isNull() | (F.col(c) == "")).count()
        null_pct[c] = round(n / total, 4) if total else 0.0

    cardinality: dict[str, int] = {
        "product_id": curated.select("__prod").distinct().count()
    }
    if "category" in mapping:
        cardinality["category"] = curated.select("__cat").distinct().count()
    if "region" in mapping:
        cardinality["region"] = curated.select("__country").distinct().count()
    if "customer_id" in mapping:
        cardinality["customer_id"] = curated.select("__cust").filter(
            F.col("__cust").isNotNull() & (F.col("__cust") != "")).distinct().count()

    numeric_summary: dict[str, dict] = {}
    qrow = curated.agg(F.min("__qty").alias("mn"), F.max("__qty").alias("mx"),
                       F.mean("__qty").alias("av")).first()
    numeric_summary["quantity"] = {"min": qrow["mn"], "max": qrow["mx"], "mean": qrow["av"],
                                  "non_numeric": quarantine_reasons.get("bad_quantity", 0)}
    prow = curated.agg(F.min("__price").alias("mn"), F.max("__price").alias("mx"),
                       F.mean("__price").alias("av")).first()
    numeric_summary["unit_price"] = {"min": prow["mn"], "max": prow["mx"], "mean": prow["av"],
                                    "non_numeric": quarantine_reasons.get("bad_price", 0)}
    rrow = curated.agg(F.sum("revenue").alias("s")).first()
    numeric_summary["revenue"] = {"min": None, "max": None, "mean": None,
                                 "non_numeric": 0, "total": rrow["s"] or 0.0}

    quarantined = sum(quarantine_reasons.values())
    accepted_count = curated.count()
    assert duplicates + quarantined + cancel_count + accepted_count == total, "quality ledger mismatch"

    grain_days = None
    if date_from and date_to:
        grain_days = (datetime.fromisoformat(date_to) - datetime.fromisoformat(date_from)).days

    return {
        "row_count": total,
        "curated_count": accepted_count,
        "duplicate_rows": duplicates,
        "unparseable_dates": bad_date,
        "unparseable_date_pct": round(bad_date / total, 4) if total else 0.0,
        "date_from": date_from,
        "date_to": date_to,
        "span_days": grain_days,
        "null_pct": null_pct,
        "cardinality": cardinality,
        "numeric_summary": numeric_summary,
        "columns": raw.columns,
        "parquet_path": str(Path(parquet_path).as_posix()),
        "quality": {
            "duplicates": duplicates,
            "quarantined": quarantined,
            "quarantine_reasons": quarantine_reasons,
            "cancellations": cancel_count,
            "cancel_abs_revenue": cancel_abs_revenue,
            "accepted": accepted_count,
        },
    }
