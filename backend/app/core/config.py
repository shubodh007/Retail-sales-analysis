"""Central settings. All runtime config comes from environment / .env.

Local development uses the defaults below (loopback PostgreSQL started via
``python scripts/pgdev.py start``). Production sets the same variable names
to Supabase / hosting values — no code changes needed (see .env.example and
docs/deployment.md).
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deployment profile: "development" | "production". Only gates
    # environment-sensitive defaults (docs, logs); behavior is identical.
    environment: str = "development"

    # Hosting platform injects PORT (Render/Cloud Run). Dev default 8000.
    port: int = 8000

    # Comma-separated allowed origins, e.g.
    # "https://retail-intel.vercel.app". Dev default is Vite's dev server.
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg2://postgres@127.0.0.1:5432/retail_intelligence"
    async_database_url: str = (
        "postgresql+asyncpg://postgres@127.0.0.1:5432/retail_intelligence"
    )

    # Filesystem workspace roots. None = <backend>/data_lake (dev default).
    # Production may point these at the container's writable tmp/ephemeral disk.
    # Both are TEMPORARY processing space; PostgreSQL is the source of truth.
    upload_dir: str | None = None
    data_dir: str | None = None

    # Resource limits (free-tier safe defaults; override per deployment).
    max_upload_mb: int = 200
    max_forecast_horizon: int = 90
    max_concurrent_jobs: int = 2

    # Models trained per forecast group run sequentially (1, the default) or
    # across N threads. Raise ONLY on machines with headroom (4+ CPUs, 8GB+):
    # each model still parallelizes internally, so workers > 1 multiplies
    # CPU/memory pressure. Measured: on a small host workers=2 was SLOWER
    # (25.8s vs ~22s sequential, global 30d). ARIMA/Prophet/RF are
    # bit-identical either way; XGB can shift ~0.3pp WAPE (parallel histogram
    # reduction) without changing selection — verified, see
    # docs/forecast-performance.md.
    forecast_max_workers: int = 1

    # Spark tuning. SPARK_MASTER="local[2]" caps cores on small containers.
    spark_master: str = "local[*]"
    spark_partitions: int = 8
    spark_driver_memory: str = "1g"

    # SQLAlchemy pool (conservative for free Supabase projects).
    db_pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    db_max_overflow: int = Field(default=5, validation_alias="DATABASE_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="DATABASE_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, validation_alias="DATABASE_POOL_RECYCLE")

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
