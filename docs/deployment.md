# Production Deployment Guide (Supabase architecture)

> Status: preparation only — nothing here deploys or provisions anything.
> Follow the sequence in §20 when you are ready to go live.

## 1. Production architecture

```
Vercel (React + Vite, static)
   │  HTTPS, fetch($VITE_API_BASE_URL/api/v1/…)
   ▼
Render — Docker container (FastAPI + uvicorn, single worker)
   │  PySpark 3.5.4 local mode · Java 17 · Prophet / XGBoost / scikit-learn
   │  BackgroundTasks workers (bounded by MAX_CONCURRENT_JOBS, one process)
   ▼
Supabase PostgreSQL (authoritative database)
   analytical marts · forecast results · RFM source · anomalies
```

Rules that never change:

- The React frontend talks **only** to FastAPI. It never touches PostgreSQL.
- No Supabase key of any kind ships to the browser. The frontend uses no
  Supabase SDK at all — `VITE_API_BASE_URL` is the only production variable.
- FastAPI connects to Supabase with ordinary PostgreSQL credentials in
  `DATABASE_URL` / `ASYNC_DATABASE_URL` (backend environment only).
- No Edge Functions, no second database, no Redis/Celery, no object store.
  The container filesystem (`UPLOAD_DIR`/`DATA_DIR`) is **temporary
  processing space**; PostgreSQL is the source of truth.

## 2. Vercel setup (frontend)

1. Import `frontend/` as the project root (or set Root Directory to
   `frontend`).
2. Build: `npm run build` (i.e. `tsc -b && vite build`), output `dist/`.
   `frontend/vercel.json` already handles SPA fallback (`/(.*)` → `/index.html`).
3. Environment variable:
   `VITE_API_BASE_URL=https://<your-backend>.onrender.com` (no trailing slash).
4. Redeploy after changing the variable (Vite inlines it at build time).

Local dev is unchanged: leave `VITE_API_BASE_URL` empty and Vite proxies
`/api` → `http://127.0.0.1:8000` (`frontend/vite.config.ts`).

## 3. Backend hosting setup (Render, Docker)

Service type: **Web Service, Docker runtime**, pointing at `backend/Dockerfile`.

- Build: `docker build -t retail-intel-backend ./backend` (Render does this).
- Start command is baked in: migrations run first, then uvicorn:
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- `--workers 1` is deliberate: the in-process job gate and the Spark
  singleton assume a single process. Scale by choosing a bigger instance,
  not more workers. (Free tier: 512 MB–1 GB RAM — see §16.)
- Health check path: `GET /api/v1/health` (one `SELECT 1`, never Spark).

Required backend environment variables (§7): `ENVIRONMENT=production`,
`DATABASE_URL`, `ASYNC_DATABASE_URL`, `CORS_ORIGINS`.

## 4. Supabase setup

1. Create a project at supabase.com (free tier is enough for the demo).
2. Project Settings → Database → copy:
   - **Direct connection** (port 5432) → `DATABASE_URL`
     (used by Alembic, the seed script, and Spark JDBC).
   - **Transaction pooler** (port 6543, `?pgbouncer=true`) → `ASYNC_DATABASE_URL`
     (used by the API at runtime).
3. Run migrations (§8), then seed demo data (§9).
4. No dashboard SQL is required. No extensions need enabling.

## 5. PostgreSQL connection setup

SQLAlchemy URL forms (placeholders only — real values live in the hosting
dashboard, never in git):

```text
DATABASE_URL=postgresql+psycopg2://postgres:<DB_PASSWORD>@db.<REF>.supabase.co:5432/postgres?sslmode=require
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres.<REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true
```

The app normalizes both (`app/db/session.py`):

- `postgres://` → `postgresql://` accepted.
- `sslmode=require` is forwarded to psycopg2/JDBC and translated to
  `ssl=require` for asyncpg (which does not understand `sslmode`).
- `pgbouncer=true` disables asyncpg's prepared-statement cache (PgBouncer
  transaction mode cannot hold them) and sets a 10 s connect timeout.

## 6. Required extensions

**None.** The schema uses only core PostgreSQL features:

- `UUID` (app-generated `uuid4`, no `uuid-ossp`/`pgcrypto` needed),
- `JSONB` (no GIN index — payloads are small metadata/config blobs),
- `timestamptz` (`now()` defaults), plain `DATE` for day-grain marts,
- `Double`/`BigInteger`/`Integer` numerics, B-tree indexes only.

No pgvector, no PostGIS, no `pg_trgm`. Migration `c41d9e2a7f30` adds the
serving indexes; verify with `\di` after migrating.

## 7. Environment variables

Backend (only variables the code actually reads — `app/core/config.py`):

| Variable | Default (dev) | Production |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` (hides `/docs`, logs CORS origins) |
| `PORT` | `8000` | injected by host |
| `DATABASE_URL` | loopback cluster | Supabase direct, `?sslmode=require` |
| `ASYNC_DATABASE_URL` | loopback cluster | Supabase pooler, `?sslmode=require&pgbouncer=true` |
| `CORS_ORIGINS` | `http://localhost:5173` | `https://<your-app>.vercel.app` (comma-separated ok) |
| `UPLOAD_DIR` / `DATA_DIR` | `backend/data_lake/...` | `/tmp/retail-intel/...` (set in image already) |
| `MAX_UPLOAD_MB` | `200` | `200` (lower, e.g. `50`, on 512 MB instances) |
| `MAX_FORECAST_HORIZON` | `90` | `90` (lower to `30` on tiny instances) |
| `MAX_CONCURRENT_JOBS` | `2` | `1` on free tier, `2` with ≥1 GB RAM |
| `SPARK_MASTER` | `local[*]` | `local[2]` on small containers |
| `SPARK_PARTITIONS` | `8` | `8` |
| `SPARK_DRIVER_MEMORY` | `1g` | `1g` (must fit the container with room for Python) |
| `POSTGRES_JDBC_JAR` | `.tools/...` (dev) | `/opt/jdbc/postgresql.jar` (set in image) |
| `DATABASE_POOL_SIZE` | `5` | `3`–`5` (free Supabase caps connections) |
| `DATABASE_MAX_OVERFLOW` | `5` | `2`–`5` |
| `DATABASE_POOL_TIMEOUT` | `30` | `30` |
| `DATABASE_POOL_RECYCLE` | `1800` | `1800` |

Frontend:

| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | FastAPI origin, no trailing slash. Empty = same origin (dev). |

Templates with placeholders only: `backend/.env.example`, `frontend/.env.example`.

## 8. Alembic migration procedure

The full production schema is reproducible from migrations — one command,
no manual SQL:

```bash
cd backend
DATABASE_URL='<supabase-direct>' alembic upgrade head
```

Chain (linear, single head): `5854c749` (datasets) → `885b4fa9` (marts) →
`6bb39d32` (forecast) → `bef5774b` (anomalies) → `c41d9e2a7f30`
(dataset `error` column + serving indexes). The Docker image runs this
automatically on every start before uvicorn boots, so a fresh database
self-initializes on first deploy.

Rollback: `alembic downgrade -1` (each migration has a tested downgrade).

## 9. Production seed procedure

The deployed app must open with a working dashboard — no 1 M-row upload by
the visitor. Seed **once** from a machine that has the canonical CSV
(the raw UCI file stays out of git; see `docs/real-dataset.md`):

```bash
cd backend
# 1. schema
DATABASE_URL='<supabase-direct>' python -m alembic upgrade head
# 2. process + load (runs Spark locally, writes marts to Supabase)
DATABASE_URL='<supabase-direct>' python scripts/seed_production.py \
  --csv <path-to-online_retail_II.csv> --filename online_retail_II.csv
# fallback when the UCI file is unavailable (clearly synthetic):
DATABASE_URL='<supabase-direct>' python scripts/seed_production.py \
  --csv ../datasets/samples/retail_synthetic.csv
```

The script is deterministic (validation → Spark profile → marts →
anomalies → `status='ready'`). Re-running creates a *new* dataset row; delete
stale rows via the API-listed ids if you re-seed. Never run seeding on app
startup and never commit the raw CSV.

## 10. Docker build/run

```bash
docker build -t retail-intel-backend ./backend
docker run -p 8000:8000 --env-file backend/.env.prod retail-intel-backend
curl localhost:8000/api/v1/health   # {"status":"ok","db":true}
```

Image contents: `python:3.12-slim` + pinned Temurin JDK 17.0.11 + PostgreSQL
JDBC 42.7.4 + `pyspark==3.5.4` (asserted at build) + Prophet/XGBoost/
scikit-learn, non-root `appuser`, `HEALTHCHECK` on `/api/v1/health`.
Java is never downloaded at runtime and `.tools/` is not used in the image.

## 11. Health endpoint

`GET /api/v1/health` → `{"status": "ok"|"degraded", "db": true|false}`.
One `SELECT 1` with pooled connection; never Spark, never model training,
safe for load-balancer probes. `/docs` and `/redoc` are disabled when
`ENVIRONMENT=production`.

## 12. CORS configuration

`CORS_ORIGINS` (comma-separated) → `allow_origins`; credentials allowed for
the listed origins only. Production must list **only** the Vercel origin(s):

```text
CORS_ORIGINS=https://retail-intel.vercel.app
```

`allow_origins=["*"]` is never used. Dev default stays
`http://localhost:5173`.

## 13. Frontend API configuration

Every API call goes through the single client `frontend/src/lib/api.ts`
(`request()` prefixes `import.meta.env.VITE_API_BASE_URL`, default `''`).
No component calls `fetch` directly; no `localhost:8000` string exists in
`frontend/src`. After pointing the variable at a new backend, rebuild
(`npm run build`) — Vite inlines the value at build time.

## 14. Dataset upload behavior

`POST /api/v1/datasets/upload` (multipart `.csv`, ≤ `MAX_UPLOAD_MB`,
filename sanitized via basename + 200-char cap, empty files rejected):

1. Streams to `UPLOAD_DIR`, validates headers against the dataset contract
   (fast, synchronous — 422 with reasons on failure, staged file removed).
2. Returns **202** `{"id", "status": "queued"}` immediately; Spark
   profiling → Parquet → marts → anomalies run in a background worker.
3. Frontend polls `GET /api/v1/datasets/{id}/status` every 3 s through
   states `queued → processing → ready | failed` (`error` carries the
   type + message only, never a traceback or path).
4. Staged CSV is deleted after processing (success or failure). Curated
   Parquet is a rebuildable intermediate; PostgreSQL is authoritative.

If all job slots are busy the upload is rejected with **429** + `Retry-After`
semantics surfaced as a busy state — it never queues silently behind a
stuck job. See §15 for the concurrency model.

## 15. Forecast job behavior

Unchanged methodology: `POST /api/v1/forecasts/runs` → 202 + group id →
`BackgroundTasks` trains ARIMA / Prophet / RandomForest / XGBoost on
chronological expanding folds, selects lowest validation WAPE (MAPE only
when mathematically valid), persists to `forecast_groups/runs/points`.
Frontend polls `GET /runs/{id}` (4 s) and renders the evidence table from
`GET /compare/{id}`.

Production guards added: slot in the same job gate as uploads (429 when
full), `MAX_FORECAST_HORIZON` enforced (422 above the limit), single
training of each requested model per group (no duplicate launches — the
group row is the idempotency record the UI polls). Identical completed
requests reuse the existing group (cache hit, no retraining); in-flight
duplicates attach to the running group. Non-ready datasets are rejected
(422). Model workers are sequential by default (`FORECAST_MAX_WORKERS=1`).

## 16. Free-tier limitations

Honest limits for a 512 MB–1 GB single container + free Supabase project:

- **One heavy job at a time** (`MAX_CONCURRENT_JOBS=1` recommended on the
  smallest instances; second request gets 429, not a silent queue).
- **Uploads ≤ 50–200 MB** depending on instance RAM (Spark holds the CSV in
  memory; the 1 M-row UCI file needs ~1 GB during profiling — seed it
  offline per §9 instead of uploading it to the live service).
- **Forecast horizons 7/30/90**; global context trains in ~1–4 min,
  product/country contexts need ≥ max(60, 2×horizon) daily points.
- **Database connections**: pool 3–5 + overflow ≤ 5; background engines use
  NullPool (open → close, never held).
- Cold starts: first request after idle may take 30–60 s (container wake +
  JVM spin-up). The 3D horizon chunk (~900 KB) stays lazy-loaded; 2D charts
  render first.
- No horizontal scaling (single worker by design), no persistent disk
  (Parquet/CSV vanish on restart — by design; data lives in Supabase).

## 17. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `alembic upgrade head` → connection refused | Wrong `DATABASE_URL` host/port or missing `?sslmode=require` for Supabase. |
| asyncpg `prepared statement already exists` | Missing `pgbouncer=true` on the pooler `ASYNC_DATABASE_URL`. |
| `Toolchain missing` / JDBC error in logs | Image without Java/JDBC (custom build) → use `backend/Dockerfile`; locally, follow `docs/java-spark-setup.md`. |
| Upload stuck in `processing` | Container restarted mid-job (ephemeral) → re-upload; row stays `processing` — re-seed or delete it. |
| 429 on upload/forecast | Job slots full → wait for the running job; raise `MAX_CONCURRENT_JOBS` only with more RAM. |
| CORS errors in browser | `CORS_ORIGINS` lacks the exact Vercel origin (no trailing slash). |
| Blank page on Vercel sub-routes | `vercel.json` rewrites missing → keep `frontend/vercel.json`. |
| API 404 from frontend | `VITE_API_BASE_URL` empty or stale build → set + rebuild. |
| ` datasets` list empty in prod | Seed not run yet → §9. |

## 18. Local → production workflow

1. Develop locally (loopback PG + `.tools` JDK + Vite proxy) — unchanged.
2. `python -m pytest tests/ -q` and `npm run build` green (§19 checks).
3. Commit (no `.env`, no `data_lake/`, no `datasets/raw/` — all gitignored).
4. Migrate Supabase (`alembic upgrade head`), seed demo data (§9).
5. Deploy backend image with prod env vars; verify `/api/v1/health` → ok.
6. Set `VITE_API_BASE_URL` on Vercel, deploy, click through every page.

## 19. Rollback strategy

- **Backend**: redeploy the previous image tag (Render keeps them). Schema
  changes are additive (`error` column + indexes) — old code runs fine on
  the new schema.
- **Migrations**: `alembic downgrade -1` reverts the latest step; never
  squash or edit a deployed migration — always add a new one.
- **Frontend**: Vercel instant-rollback to the previous deployment; the API
  contract is unchanged (additive `error` / `status` fields only).
- **Data**: re-seeding creates new dataset rows; point the UI at the new
  dataset before deleting the old one.
