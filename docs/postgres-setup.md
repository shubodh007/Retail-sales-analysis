# PostgreSQL Setup (local development + deployment)

PostgreSQL is the primary database. There is NO SQLite fallback —
no SQLite-specific code paths exist in this project.

## Local development (implemented)

No admin install. Real PostgreSQL 16 binaries are bootstrapped by the
`pgserver` package into the project venv; the cluster lives in
`.tools/pgdata` (gitignored).

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/pgdev.py start   # init on first run, start on 127.0.0.1:5432
python scripts/pgdev.py uri     # print SYNC/ASYNC URIs
python scripts/pgdev.py stop    # stop, keep data
```

- Database: `retail_intelligence` (tests use `retail_intelligence_test`).
- Auth: trust on loopback (dev only). Deployment uses password/Managed PG
  via `DATABASE_URL` / `ASYNC_DATABASE_URL` in `.env` (see `.env.example`).
- Migrations: `python -m alembic upgrade head` (sync engine, Postgres-native
  types: UUID, JSONB, timestamptz).

## Verify before continuing (Phase 1 gate)

```powershell
python scripts/pgdev.py start
python -m alembic upgrade head
python -m pytest tests/ -q
```

All three must succeed. If PostgreSQL is unavailable, STOP — do not
substitute SQLite. Document the blocker and resolve it first.

## Deployment

Provision managed Postgres 16+ (or the same `pgdev` layout on a VM),
set the two `*_DATABASE_URL` vars, run `alembic upgrade head`.
No code changes: SQLAlchemy + Alembic are Postgres-first throughout.

## Known limitation (local pgserver build)

The pgserver Windows binaries ship without the tzdata directory, so the
local server only knows `GMT` (named zones like `UTC` are rejected).
The app therefore pins Spark/JVM zones to `GMT`, which is
instant-identical to UTC — all dataset dates stay UTC-normalized.
Managed Postgres deployments have full tzdata; no change needed there.
