# Retail Intelligence — Retail Sales Data Analysis & Forecasting

Industrial Analytics + Data Observatory + Forecasting Workstation.

## Status

Phase 1 foundation (vertical slice: CSV → FastAPI → validation →
PySpark → profiling → Parquet → PostgreSQL → React Data Lab).

See `docs/` for the dataset contract, architecture notes, and setup guides.

## Production

Target: Vercel (frontend) → container host (FastAPI + PySpark) →
Supabase PostgreSQL. **Not deployed yet.**

Full preparation guide: [`docs/deployment.md`](docs/deployment.md)
(environment matrix, `alembic upgrade head`, one-shot seed script,
Docker build, CORS, free-tier limits, rollback).

## Layout

- `frontend/` — Vite + React + TypeScript app
- `backend/` — FastAPI + PySpark + SQLAlchemy/Alembic (PostgreSQL-first)
- `datasets/samples/` — deterministic synthetic sample (testing/fallback only)
- `docs/` — architecture, dataset provenance, setup guides

> Synthetic data is NEVER presented as real-world data.
> Primary demonstration dataset: UCI Online Retail II (see
> `docs/real-dataset.md`).
