"""RFM segmentation. Deterministic rules, no clustering, fully documented.

Inputs per customer: recency_days (dataset_end - last purchase), frequency
(orders), monetary (revenue). Scores: quintile ranks 1..5 (R reversed so 5 =
most recent). Segments assigned by first-match priority rules below.
Clustering was considered and rejected: 5.9K customers segment cleanly with
auditable rules; no latent structure justifies k-means here.
"""
from datetime import date


def _quintile(ranks: list[float], reverse: bool = False) -> list[int]:
    order = sorted(range(len(ranks)), key=lambda i: ranks[i], reverse=reverse)
    scores = [0] * len(ranks)
    n = len(ranks)
    for pos, i in enumerate(order):
        scores[i] = min(5, 1 + (pos * 5) // max(1, n))
    return scores


SEGMENT_RULES = [
    ("New", lambda r, f, m: f == 1),
    ("Champions", lambda r, f, m: r >= 4 and f >= 4),
    ("At-risk", lambda r, f, m: r <= 2 and f >= 3),
    ("Loyal", lambda r, f, m: f >= 4),
    ("Promising", lambda r, f, m: r >= 4),
    ("Hibernating", lambda r, f, m: r <= 2),
    ("Steady", lambda r, f, m: True),
]


def segment(r: int, f: int, m: int) -> str:
    for name, rule in SEGMENT_RULES:
        if rule(r, f, m):
            return name
    return "Steady"


def compute_rfm(customers: list[dict], end: date) -> dict:
    """customers: [{customer_id, country, orders, revenue, last_date}]. Pure."""
    if not customers:
        return {"segments": [], "customers": []}
    rec = [(end - c["last_date"]).days if c["last_date"] else 9999 for c in customers]
    frq = [c["orders"] for c in customers]
    mon = [c["revenue"] for c in customers]
    rs, fs, ms = _quintile(rec, reverse=True), _quintile(frq), _quintile(mon)
    enriched = []
    for c, d, r, f, m in zip(customers, rec, rs, fs, ms):
        enriched.append({**c, "recency_days": d, "r": r, "f": f, "m": m,
                         "segment": segment(r, f, m)})
    agg: dict[str, dict] = {}
    for e in enriched:
        a = agg.setdefault(e["segment"], {"segment": e["segment"], "customers": 0, "revenue": 0.0,
                                          "orders": 0})
        a["customers"] += 1
        a["revenue"] += e["revenue"]
        a["orders"] += e["orders"]
    total_rev = sum(a["revenue"] for a in agg.values()) or 1.0
    for a in agg.values():
        a["revenue"] = round(a["revenue"], 2)
        a["revenue_share"] = round(a["revenue"] / total_rev, 4)
    return {"segments": sorted(agg.values(), key=lambda a: -a["revenue"]),
            "customers": sorted(enriched, key=lambda e: -e["revenue"])}
