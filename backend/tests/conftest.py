"""Phase 1 tests: mapping units, health, full upload vertical slice (PG + Spark)."""
import time
import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db.session import Base
import app.models.dataset  # noqa: F401
import app.models.marts  # noqa: F401
import app.models.forecast  # noqa: F401
import app.models.anomaly  # noqa: F401
from app.db.session import request_session
from app.main import app  # noqa: F401 (registers routers)

TEST_SYNC_URL = "postgresql+psycopg2://postgres@127.0.0.1:5432/retail_intelligence_test"
TEST_ASYNC_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/retail_intelligence_test"


def _ensure_test_db():
    conn = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", dbname="postgres")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'retail_intelligence_test'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE retail_intelligence_test")
    conn.close()


@pytest.fixture(scope="session")
def client():
    _ensure_test_db()
    engine = create_engine(TEST_SYNC_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async_engine = create_async_engine(TEST_ASYNC_URL)
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _test_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[request_session] = _test_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def mini_csv(tmp_path):
    p = tmp_path / f"mini_{uuid.uuid4().hex[:8]}.csv"
    p.write_text(
        "InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country\n"
        "536365,85123A,WHITE HANGING HEART,6,12/01/2010 08:26,2.55,17850,United Kingdom\n"
        "536365,71053,WHITE METAL LANTERN,6,12/01/2010 08:26,3.39,17850,United Kingdom\n"
        "536366,84406B,CREAM CUPID HEARTS COAT HANGER,8,12/01/2010 08:28,2.75,,France\n"
        "C536367,84879,ASSORTED COLOUR BIRD ORNAMENT,-1,12/02/2010 09:00,1.69,17850,United Kingdom\n"
    )
    return p


@pytest.fixture()
def bad_csv(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("foo,bar\n1,2\n")
    return p


@pytest.fixture()
def narrow_csv(tmp_path):
    """Date + product + qty/price only: no customer, no geography."""
    p = tmp_path / "narrow.csv"
    p.write_text(
        "InvoiceNo,StockCode,Quantity,InvoiceDate,UnitPrice\n"
        "1,A001,2,2024-03-01 10:00:00,5.00\n"
        "2,A002,1,2024-03-02 10:00:00,9.50\n"
    )
    return p


def upload_and_wait(client, path, name, timeout=600):
    """POST /datasets/upload (202) then poll /status until ready.

    Works whether the test server runs background tasks inline (TestClient)
    or truly in the background (live server).
    """
    with open(path, "rb") as f:
        r = client.post("/api/v1/datasets/upload", files={"file": (name, f, "text/csv")})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    dataset_id = r.json()["id"]
    deadline = time.time() + timeout
    while True:
        s = client.get(f"/api/v1/datasets/{dataset_id}/status")
        assert s.status_code == 200, s.text
        body = s.json()
        if body["status"] == "ready":
            return dataset_id
        assert body["status"] in ("queued", "processing"), body
        assert time.time() < deadline, f"dataset {dataset_id} never ready: {body}"
        time.sleep(2)
