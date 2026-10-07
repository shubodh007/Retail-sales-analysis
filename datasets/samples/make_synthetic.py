"""Deterministic synthetic retail sample. Stdlib only. Seed 42.

Output: retail_synthetic.csv (~2 years daily, UCI-compatible columns + Category).
Intraday invoices are aggregated to one row per product/region/day for size.
See docs/synthetic-dataset.md — NEVER present this as real-world data.
"""
import csv
import math
import random
from datetime import date, timedelta

SEED = 42
START = date(2022, 1, 1)
DAYS = 730
OUT = "retail_synthetic.csv"

PRODUCTS = [
    ("P01", "CERAMIC MUG BLUE", "Kitchen", 4.95),
    ("P02", "CERAMIC MUG RED", "Kitchen", 4.95),
    ("P03", "STEEL LUNCHBOX", "Kitchen", 12.50),
    ("P04", "WOOL SCARF GREY", "Apparel", 18.00),
    ("P05", "WOOL SCARF NAVY", "Apparel", 18.00),
    ("P06", "COTTON TOTE NATURAL", "Apparel", 6.25),
    ("P07", "GLASS VASE SMALL", "Decor", 9.75),
    ("P08", "GLASS VASE LARGE", "Decor", 15.25),
    ("P09", "CANDLE VANILLA", "Decor", 7.50),
    ("P10", "CANDLE CINNAMON", "Decor", 7.50),
    ("P11", "NOTEBOOK A5 LINED", "Office", 5.40),
    ("P12", "PEN SET BLACK 3PK", "Office", 8.90),
]
REGIONS = [("United Kingdom", 0.46), ("Germany", 0.22), ("France", 0.18), ("Spain", 0.14)]
CUSTOMERS = [f"{17000 + i}" for i in range(400)]

ANOMALIES = {  # (date, region|None, product|None, qty_mult, price_mult)
    (date(2022, 11, 25), "United Kingdom", "P04", 8.0, 1.0),
    (date(2023, 2, 14), None, None, 0.15, 1.0),
}


def price_mult(day: date, code: str) -> float:
    if code == "P09" and date(2023, 7, 1) <= day <= date(2023, 7, 7):
        return 0.5
    return 1.0


def main() -> None:
    rnd = random.Random(SEED)
    invoice = 700000
    rows = []
    for d in range(DAYS):
        day = START + timedelta(days=d)
        dow = day.weekday()
        weekly = 1.0 + (0.45 if dow in (5, 6) else -0.15 if dow == 1 else 0.0)
        annual = 1.0 + 0.55 * math.exp(-(((day.timetuple().tm_yday - 358) / 18) ** 2))
        trend = 1.0 + 0.0009 * d
        for code, desc, cat, base_price in PRODUCTS:
            for region, share in REGIONS:
                lam = 3.2 * share * weekly * annual * trend
                qty = max(0, round(rnd.gauss(lam, lam * 0.35)))
                mult, pm = 1.0, price_mult(day, code)
                for ad, ar, ap, qm, _ in ANOMALIES:
                    if ad == day and (ar is None or ar == region) and (ap is None or ap == code):
                        mult = qm
                qty = max(0, round(qty * mult))
                if qty == 0:
                    continue
                invoice += 1
                cust = rnd.choice(CUSTOMERS) if rnd.random() > 0.06 else ""
                rows.append([
                    invoice, code, desc, qty,
                    day.strftime("%m/%d/%Y %H:%M"), f"{base_price * pm:.2f}", cust, region, cat,
                ])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
                    "UnitPrice", "CustomerID", "Country", "Category"])
        w.writerows(rows)
    print(f"wrote {OUT}: {len(rows)} rows, {DAYS} days")


if __name__ == "__main__":
    main()
