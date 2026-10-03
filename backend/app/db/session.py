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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


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


def sync_url_from_async(async_url: str) -> str:
    """Derive the sync (psycopg2) URL for the bound async session URL."""
    scheme, rest, query = _split_url(async_url)
    return normalize_sync_url(_join_url("postgresql", rest, query))


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


def make_job_engine(url: str):
    """Short-lived engine for background threads (Spark marts, forecast jobs).

    NullPool: the worker opens a few connections and closes them; nothing is
    held between jobs, so a free-tier connection limit is never exhausted.
    """
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
