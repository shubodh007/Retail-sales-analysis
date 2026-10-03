"""Regression test: ingestion worker must use the Supabase pooler username.

Root cause (Render log):
    ingest <id> failed: psycopg2.OperationalError:
    FATAL: password authentication failed for user "postgres"

Both DATABASE_URL and ASYNC_DATABASE_URL held the pooler user
``postgres.<project>``, yet the worker authenticated as plain ``postgres``.

Two defects combined:

1. ``sync_url_from_async(str(session.get_bind().url))`` used ``str(URL)``,
   which SQLAlchemy 2.x renders with the password masked to ``***``. The
   background sync engine therefore always connected with the wrong
   password; Supabase pooler reports that failure against the underlying
   DB user ``postgres`` (suffix stripped), hiding the real pooler username.
2. ``marts._targets`` / ``anomalies`` silently fell back to
   ``u.username or "postgres"``, turning any URL-parsing failure into a
   wrong-user auth attempt instead of a clear configuration error.

This test proves the worker path preserves the intended pooler username
(and never the ``postgres`` fallback or a masked password), without
hardcoding credentials or logging secrets.
"""
from sqlalchemy.engine import make_url

from app.db.session import (
    describe_url_safe,
    normalize_sync_url,
    resolve_job_sync_url,
    sync_url_from_async,
)
from app.services.marts import _targets

POOLER_USER = "postgres.tmzhhmiehmuycbnsvfyu"
POOLER_HOST = "aws-0-ap-south-1.pooler.supabase.com"
POOLER_DB = "postgres"

SYNC_5432 = (
    f"postgresql+psycopg2://{POOLER_USER}:s3cret-pw"
    f"@{POOLER_HOST}:5432/{POOLER_DB}?sslmode=require"
)
ASYNC_6543 = (
    f"postgresql+asyncpg://{POOLER_USER}:s3cret-pw"
    f"@{POOLER_HOST}:6543/{POOLER_DB}?sslmode=require&pgbouncer=true"
)


def test_sync_url_from_async_preserves_pooler_username():
    derived = sync_url_from_async(ASYNC_6543)
    info = describe_url_safe(derived)
    assert info["username"] == POOLER_USER, info
    assert info["username"] != "postgres"
    assert info["host"] == POOLER_HOST
    assert info["database"] == POOLER_DB
    # Password must survive (not masked): the old str(URL) bug produced ***.
    assert ":***@" not in derived
    assert "s3cret-pw" in derived


def test_sync_url_from_async_rejects_masked_password():
    masked = (
        f"postgresql+asyncpg://{POOLER_USER}:***"
        f"@{POOLER_HOST}:6543/{POOLER_DB}?ssl=require"
    )
    try:
        sync_url_from_async(masked)
    except ValueError as exc:
        assert "***" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("masked URL was not rejected")


def test_sync_url_from_async_accepts_url_object_without_masking():
    url_obj = make_url(ASYNC_6543)
    # str() masks (the old bug); the fixed path must not use str().
    assert ":***@" in str(url_obj)
    derived = sync_url_from_async(url_obj)
    assert describe_url_safe(derived)["username"] == POOLER_USER
    assert ":***@" not in derived


def test_marts_targets_preserve_pooler_username():
    jdbc, pg = _targets(SYNC_5432, source="DATABASE_URL")
    assert pg["user"] == POOLER_USER, pg
    assert pg["user"] != "postgres"
    assert pg["host"] == POOLER_HOST
    assert pg["port"] == 5432
    assert pg["dbname"] == POOLER_DB
    assert "sslmode=require" in jdbc


def test_marts_targets_reject_masked_password():
    masked = SYNC_5432.replace("s3cret-pw", "***")
    try:
        _targets(masked)
    except ValueError as exc:
        assert "***" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("masked URL was not rejected")


def test_marts_targets_reject_missing_username():
    no_user = f"postgresql+psycopg2://{POOLER_HOST}:5432/{POOLER_DB}?sslmode=require"
    try:
        _targets(no_user)
    except ValueError as exc:
        assert "username" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("missing username was not rejected")


def test_resolve_job_sync_url_uses_database_url_in_prod(monkeypatch):
    """Prod: bind (6543 transaction pooler) + settings (5432 session pooler)
    share database ``postgres`` -> worker must use DATABASE_URL (5432)
    with the pooler username."""
    from app.core.config import get_settings
    import app.db.session as sess

    get_settings.cache_clear()
    sess.reset_engines()
    monkeypatch.setenv(
        "DATABASE_URL", SYNC_5432,
    )
    monkeypatch.setenv(
        "ASYNC_DATABASE_URL", ASYNC_6543,
    )
    get_settings.cache_clear()
    try:
        bound = make_url(ASYNC_6543)
        sync_url, source = resolve_job_sync_url(bound)
        assert source == "DATABASE_URL", source
        info = describe_url_safe(sync_url)
        assert info["username"] == POOLER_USER, info
        assert info["host"] == POOLER_HOST
        assert info["port"] == 5432, info
        assert info["database"] == POOLER_DB
    finally:
        get_settings.cache_clear()
        sess.reset_engines()


def test_resolve_job_sync_url_preserves_test_binding(monkeypatch):
    """Tests override request_session to the *_test DB: the worker must stay
    on the bound test database, never jump to settings (production)."""
    from app.core.config import get_settings
    import app.db.session as sess

    get_settings.cache_clear()
    sess.reset_engines()
    monkeypatch.setenv(
        "DATABASE_URL", SYNC_5432,
    )
    monkeypatch.setenv(
        "ASYNC_DATABASE_URL", ASYNC_6543,
    )
    get_settings.cache_clear()
    try:
        test_bind = make_url(
            "postgresql+asyncpg://postgres@127.0.0.1:5432/retail_intelligence_test"
        )
        sync_url, source = resolve_job_sync_url(test_bind)
        info = describe_url_safe(sync_url)
        assert info["database"] == "retail_intelligence_test", info
        assert source == "request-session-bind", source
    finally:
        get_settings.cache_clear()
        sess.reset_engines()


def test_describe_url_safe_never_leaks_password():
    info = describe_url_safe(SYNC_5432)
    assert info["username"] == POOLER_USER
    assert "password" not in info
    assert "s3cret-pw" not in str(info)
    normalized = normalize_sync_url(SYNC_5432)
    assert describe_url_safe(normalized)["username"] == POOLER_USER
