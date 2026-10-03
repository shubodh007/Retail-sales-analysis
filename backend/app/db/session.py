"""Async engine/session + sync engine for Alembic and background jobs.

PostgreSQL only (local cluster in dev, Supabase in production — both speak
the same SQLAlchemy URLs). Handles Supabase connection details:

- ``?sslmode=require`` is forwarded to psycopg2/JDBC and translated to
  ``?ssl=require`` for asyncpg (which does not understand ``sslmode``).
- ``?pgbouncer=true`` (Supabase transaction pooler on port 6543) disables
  asyncpg's prepared-statement cache, which PgBouncer cannot support.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


_job_log = None


def _job_logger():
    global _job_log
    if _job_log is None:
        import logging
        _job_log = logging.getLogger("retail-intelligence")
    return _job_log


def describe_url_safe(url: str) -> dict:
    """Parse a SQLAlchemy URL for diagnostics WITHOUT secrets.

    Returns {driver, username, host, port, database}. Never includes
    password or the full URL. Safe to log.
    """
    try:
        u = make_url(url)
        return {
            "driver": u.drivername,
            "username": u.username,
            "host": u.host,
            "port": u.port,
            "database": u.database,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}"}


def log_job_target(source: str, url: str, job: str) -> None:
    """Temporary safe diagnostics before opening a sync connection.

    Logs only source env-var name, parsed username, hostname, port,
    database, and driver. Never logs passwords, complete URLs, or secrets.
    """
    info = describe_url_safe(url)
    _job_logger().info(
        "job db target job=%s source=%s driver=%s user=%s host=%s port=%s db=%s",
        job, source, info.get("driver"), info.get("username"),
        info.get("host"), info.get("port"), info.get("database"),
    )


class Base(DeclarativeBase):
    pass


def _split_url(url: str):
    """Split a SQLAlchemy URL into (prefix, hostport-path-part, query dict).

    Works for ``postgresql+psycopg2://``, ``postgresql+asyncpg://`` and
    bare ``postgresql://`` / ``postgres://`` forms.
    """
    scheme, rest = url.split("://", 1)
    if "?" in rest:
        rest, _, qs = rest.partition("?")
        query = dict(parse_qsl(qs, keep_blank_values=True))
    else:
        query = {}
    return scheme, rest, query


def _join_url(scheme: str, rest: str, query: dict) -> str:
    if query:
        return f"{scheme}://{rest}?{urlencode(query)}"
    return f"{scheme}://{rest}"


def normalize_async_url(url: str) -> tuple[str, dict]:
    """Return (asyncpg-ready URL, connect_args) for a configured URL."""
    scheme, rest, query = _split_url(url)
    if scheme == "postgres":
        scheme = "postgresql"
    if not scheme.endswith("+asyncpg"):
        scheme = "postgresql+asyncpg"
    connect_args: dict = {"timeout": 10}
    # asyncpg uses `ssl=`; translate libpq-style `sslmode=` when present.
    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = "require" if sslmode in ("require", "verify-ca", "verify-full") else sslmode
    # PgBouncer transaction pooling cannot hold prepared statements.
    if query.pop("pgbouncer", None) == "true":
        connect_args["statement_cache_size"] = 0
    return _join_url(scheme, rest, query), connect_args


def normalize_sync_url(url: str) -> str:
    """Return a psycopg2-ready URL (keeps ``sslmode`` for libpq)."""
    scheme, rest, query = _split_url(url)
    if scheme == "postgres":
        scheme = "postgresql"
    if not scheme.endswith("+psycopg2"):
        scheme = "postgresql+psycopg2"
    query.pop("pgbouncer", None)  # internal flag only; not a libpq parameter
    return _join_url(scheme, rest, query)


def sync_url_from_async(async_url) -> str:
    """Derive a psycopg2 URL from an asyncpg URL.

    Accepts a raw string or a SQLAlchemy URL object. URL objects MUST be
    rendered with ``hide_password=False``: plain ``str(URL)`` masks the
    password to ``***`` (SQLAlchemy 2.x), which makes every background
    worker authenticate with the wrong password — Supabase pooler then
    reports ``password authentication failed for user "postgres"``
    (the underlying DB user, suffix stripped), even though the env vars
    hold the correct ``postgres.<project>`` pooler username.

    Refuses masked (``***``) input fail-fast instead of attempting a
    connection that can only fail with a misleading wrong-user message.
    """
    if hasattr(async_url, "render_as_string"):
        # SQLAlchemy URL object: preserve the real password.
        async_url = async_url.render_as_string(hide_password=False)
    if ":***@" in async_url:
        raise ValueError(
            "refusing masked database URL (password is '***'): "
            "pass a URL object via render_as_string(hide_password=False), "
            "never str(URL)"
        )
    scheme, rest, query = _split_url(async_url)

    # asyncpg uses `ssl`; psycopg2/libpq expects `sslmode`.
    ssl = query.pop("ssl", None)
    if ssl and "sslmode" not in query:
        query["sslmode"] = ssl

    return normalize_sync_url(_join_url("postgresql", rest, query))


def resolve_job_sync_url(bound_url=None) -> tuple[str, str]:
    """Return (sync_url, source) for background sync workers.

    Background jobs (ingestion, forecast training, Spark JDBC, raw
    psycopg2) are sync psycopg2 work and must use ``DATABASE_URL``
    (Supabase session pooler on 5432 in production) — never a URL derived
    from the async transaction pooler (6543), and never a ``str(URL)``
    rendering that masks the password to ``***``.

    Test isolation is preserved: when the request session is bound to a
    different database than settings (tests override ``request_session``
    to the ``*_test`` database), the bound database is used so workers
    read/write the test DB, not production. Returns the source
    env-var/binding name for safe diagnostics.
    """
    settings = get_settings()
    settings_sync = normalize_sync_url(settings.database_url)
    if bound_url is None:
        return settings_sync, "DATABASE_URL"
    if hasattr(bound_url, "render_as_string"):
        bound_full = bound_url.render_as_string(hide_password=False)
    else:
        bound_full = bound_url
    if ":***@" in bound_full:
        # Masked rendering lost the password — fall back to settings,
        # which holds the real password (never masked).
        return settings_sync, "DATABASE_URL"
    try:
        bound_info = describe_url_safe(sync_url_from_async(bound_full))
        settings_info = describe_url_safe(settings_sync)
    except ValueError:
        return settings_sync, "DATABASE_URL"
    # Different database name => test/local override (e.g. *_test):
    # stay on the bound DB so workers never touch production.
    if (bound_info.get("database") and settings_info.get("database")
            and bound_info.get("database") != settings_info.get("database")):
        return sync_url_from_async(bound_full), "request-session-bind"
    return settings_sync, "DATABASE_URL"


def _pool_kwargs() -> dict:
    s = get_settings()
    return {
        "pool_size": s.db_pool_size,
        "max_overflow": s.db_max_overflow,
        "pool_timeout": s.db_pool_timeout,
        "pool_recycle": s.db_pool_recycle,
        "pool_pre_ping": True,
    }


def _urls():
    s = get_settings()
    return s.async_database_url, s.database_url


_async_engine = None
_session_factory = None


def reset_engines() -> None:
    """Drop cached engines (tests / settings changes)."""
    global _async_engine, _session_factory
    _async_engine = None
    _session_factory = None


def get_session_factory():
    global _async_engine, _session_factory
    if _session_factory is None:
        async_url, _ = _urls()
        url, connect_args = normalize_async_url(async_url)
        _async_engine = create_async_engine(url, connect_args=connect_args, **_pool_kwargs())
        _session_factory = async_sessionmaker(_async_engine, expire_on_commit=False)
    return _session_factory


def get_sync_engine():
    _, sync_url = _urls()
    return create_engine(normalize_sync_url(sync_url), **_pool_kwargs())


def make_job_engine(url: str, source: str = "unknown"):
    """Short-lived engine for background threads (Spark marts, forecast jobs).

    NullPool: the worker opens a few connections and closes them; nothing is
    held between jobs, so a free-tier connection limit is never exhausted.

    Logs safe diagnostics (source, driver, user, host, port, db — never
    secrets) immediately before the connection is built, and refuses
    masked-password URLs fail-fast.
    """
    if ":***@" in url:
        raise ValueError(
            f"refusing masked database URL from source={source}: "
            "password is '***' (str(URL) masking). Use "
            "render_as_string(hide_password=False) or DATABASE_URL."
        )
    log_job_target(source, normalize_sync_url(url), "make_job_engine")
    return create_engine(normalize_sync_url(url), poolclass=NullPool,
                         pool_pre_ping=True, connect_args={"connect_timeout": 10})


async def check_db() -> bool:
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        import logging
        logging.getLogger("retail-intelligence").exception(
            "Async database health check failed"
        )
        return False


async def request_session():
    """Single request-session dependency shared by all routers (and tests)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
