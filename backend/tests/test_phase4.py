"""Phase 4 tests: RFM rules, anomaly detector, new-endpoint gating."""
from datetime import date

from app.services import rfm as rfm_svc
from app.services.anomalies import THRESHOLD, detect_points
from tests.conftest import upload_and_wait


def _cust(cid, orders, revenue, last):
    return {"customer_id": cid, "country": "UK", "orders": orders,
            "revenue": revenue, "last_date": last}


def test_rfm_segments_are_deterministic():
    end = date(2024, 1, 31)
    customers = [_cust("new", 1, 10.0, date(2024, 1, 30)),
                 *[_cust(f"c{i}", 10, 500.0, date(2024, 1, 29)) for i in range(8)],
                 *[_cust(f"old{i}", 10, 500.0, date(2023, 6, 1)) for i in range(4)]]
    out = rfm_svc.compute_rfm(customers, end)
    by_id = {c["customer_id"]: c for c in out["customers"]}
    assert by_id["new"]["segment"] == "New"
    assert by_id["old0"]["segment"] in ("Hibernating", "At-risk")
    # revenue shares sum to ~1
    assert abs(sum(s["revenue_share"] for s in out["segments"]) - 1.0) < 0.01
    # segments sorted by revenue desc
    revs = [s["revenue"] for s in out["segments"]]
    assert revs == sorted(revs, reverse=True)


def test_rfm_rule_priority():
    assert rfm_svc.segment(5, 1, 5) == "New"  # F==1 beats everything
    assert rfm_svc.segment(5, 5, 5) == "Champions"
    assert rfm_svc.segment(1, 5, 3) == "At-risk"  # lapsed frequency outranks loyalty
    assert rfm_svc.segment(4, 5, 3) == "Champions"
    assert rfm_svc.segment(3, 5, 3) == "Loyal"
    assert rfm_svc.segment(1, 2, 1) == "Hibernating"
    assert rfm_svc.segment(3, 3, 3) == "Steady"


def test_rfm_empty():
    assert rfm_svc.compute_rfm([], date(2024, 1, 1)) == {"segments": [], "customers": []}


def test_detector_flags_spike_not_baseline():
    dates = [f"2024-01-{d:02d}" for d in range(1, 61)]
    vals = [100.0] * 60
    vals[40] = 500.0
    hits = detect_points(dates, vals)
    assert len(hits) == 1
    assert hits[0]["date"] == dates[40]
    assert hits[0]["observed"] == 500.0
    assert abs(hits[0]["deviation"]) >= THRESHOLD
    assert 90 < hits[0]["expected"] < 110


def test_detector_quiet_on_flat():
    dates = [f"2024-01-{d:02d}" for d in range(1, 61)]
    assert detect_points(dates, [50.0] * 60) == []  # zero MAD -> no flags


def test_detector_adapts_to_level_shift():
    # Step change: transition days flag, then the trailing baseline adapts
    # and the new level goes quiet. Ramps never flag (correct: no outlier
    # versus their own trailing window).
    dates = [f"d{i}" for i in range(90)]
    vals = [100.0] * 45 + [200.0] * 45
    hits = detect_points(dates, vals)
    assert len(hits) > 0
    assert all(h["date"] < "d60" for h in hits)  # quiet after adaptation
    dates2 = [f"d{i}" for i in range(60)]
    assert detect_points(dates2, [float(i) for i in range(60)]) == []


def test_detector_uses_trailing_window_only():
    # A dip AFTER a spike must not rewrite the spike's own baseline:
    # baseline at spike time sees only pre-spike values.
    dates = [f"d{i}" for i in range(60)]
    vals = [100.0] * 60
    vals[40] = 500.0
    vals[41] = 10.0
    hits = {h["date"]: h for h in detect_points(dates, vals)}
    assert abs(hits["d40"]["expected"] - 100.0) < 5.0


def test_rfm_gating_on_narrow(client, narrow_csv):
    did = upload_and_wait(client, narrow_csv, "n.csv")
    assert client.get("/api/v1/analytics/customers/rfm",
                      params={"dataset_id": did}).status_code == 409
    # global anomalies need no dimension: honest empty, not 409
    r = client.get("/api/v1/analytics/anomalies", params={"dataset_id": did})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    r = client.get("/api/v1/analytics/anomalies/summary", params={"dataset_id": did})
    assert r.status_code == 200
    assert r.json()["by_dimension"] == {}


def test_anomaly_api_validation(client, mini_csv):
    did = upload_and_wait(client, mini_csv, "m.csv")
    r = client.get("/api/v1/analytics/anomalies",
                   params={"dataset_id": did, "dimension": "nope"})
    assert r.status_code == 422
