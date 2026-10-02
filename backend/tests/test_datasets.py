"""Vertical slice tests: health, async upload -> Spark -> Parquet -> marts -> PG -> API."""

from tests.conftest import upload_and_wait


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def _upload_raw(client, path, name):
    with open(path, "rb") as f:
        return client.post("/api/v1/datasets/upload", files={"file": (name, f, "text/csv")})


def test_upload_accepts_and_queues(client, mini_csv):
    r = _upload_raw(client, mini_csv, "mini.csv")
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    dataset_id = r.json()["id"]

    s = client.get(f"/api/v1/datasets/{dataset_id}/status")
    assert s.status_code == 200
    assert s.json()["status"] in ("queued", "processing", "ready")


def test_upload_mini_csv(client, mini_csv):
    dataset_id = upload_and_wait(client, mini_csv, "mini.csv")

    r = client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == dataset_id
    assert body["status"] == "ready"
    assert body["row_count"] == 4
    assert body["schema_map"]["date"] == "InvoiceDate"
    # 1 cancellation quarantined out of revenue path, 3 accepted
    assert body["profile"]["curated_count"] == 3
    assert body["profile"]["quality"]["cancellations"] == 1
    assert body["profile"]["quality"]["accepted"] == 3
    assert body["profile"]["marts"]["sales_daily"] == 1  # all accepted rows share one day
    assert body["profile"]["cardinality"]["product_id"] == 3

    r3 = client.get("/api/v1/datasets")
    assert r3.status_code == 200
    assert any(d["id"] == dataset_id for d in r3.json())
    return dataset_id


def test_analytics_on_mini_csv(client, mini_csv):
    dataset_id = test_upload_mini_csv(client, mini_csv)

    ov = client.get("/api/v1/analytics/overview", params={"dataset_id": dataset_id})
    assert ov.status_code == 200
    body = ov.json()
    # accepted: 6*2.55 + 6*3.39 + 8*2.75 = 15.30 + 20.34 + 22.00
    assert abs(body["totals"]["revenue"] - 57.64) < 0.01
    assert body["totals"]["orders"] == 2
    assert body["dataset"]["capabilities"]["customers"] is True
    assert body["dataset"]["capabilities"]["geography"] is True
    assert len(body["daily"]) == 1
    assert len(body["top_countries"]) == 2

    pr = client.get("/api/v1/analytics/products", params={"dataset_id": dataset_id})
    assert pr.status_code == 200
    assert pr.json()["total"] == 3
    assert pr.json()["items"][0]["stockcode"] == "84406B"  # highest revenue first

    tr = client.get("/api/v1/analytics/sales/trend",
                    params={"dataset_id": dataset_id, "grain": "daily"})
    assert tr.status_code == 200
    assert len(tr.json()["points"]) == 1

    geo = client.get("/api/v1/analytics/geography", params={"dataset_id": dataset_id})
    assert geo.status_code == 200
    assert {c["country"] for c in geo.json()["countries"]} == {"United Kingdom", "France"}

    cu = client.get("/api/v1/analytics/customers", params={"dataset_id": dataset_id})
    assert cu.status_code == 200
    assert cu.json()["total"] == 1  # guest row excluded from customer mart

    cap = client.get("/api/v1/analytics/capabilities", params={"dataset_id": dataset_id})
    assert cap.json()["capabilities"]["category"] is False


def test_capability_gating(client, narrow_csv):
    dataset_id = upload_and_wait(client, narrow_csv, "narrow.csv")

    assert client.get("/api/v1/analytics/customers",
                      params={"dataset_id": dataset_id}).status_code == 409
    assert client.get("/api/v1/analytics/geography",
                      params={"dataset_id": dataset_id}).status_code == 409
    ov = client.get("/api/v1/analytics/overview", params={"dataset_id": dataset_id})
    assert ov.status_code == 200
    assert ov.json()["top_countries"] == []
    assert ov.json()["dataset"]["capabilities"]["customers"] is False


def test_upload_rejects_bad_schema(client, bad_csv):
    assert _upload_raw(client, bad_csv, "bad.csv").status_code == 422


def test_upload_rejects_non_csv(client, mini_csv):
    assert _upload_raw(client, mini_csv, "mini.txt").status_code == 422
