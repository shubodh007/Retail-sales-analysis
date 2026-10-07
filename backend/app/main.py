"""FastAPI entrypoint. REST only; browser receives aggregates, never raw rows."""
import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.analytics import router as analytics_router
from app.api.datasets import router as datasets_router
from app.api.forecasts import router as forecasts_router
from app.core.config import get_settings
from app.db.session import check_db
from app.services.demo import seed_demo_if_needed

log = logging.getLogger("retail-intelligence")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Do not block health checks or the event loop while Spark builds demo marts.
    bootstrap_task = asyncio.create_task(asyncio.to_thread(seed_demo_if_needed))
    try:
        yield
    finally:
        if not bootstrap_task.done():
            bootstrap_task.cancel()


app = FastAPI(title="Retail Intelligence API", version="0.1.0",
              docs_url=None if settings.is_production else "/docs",
              redoc_url=None if settings.is_production else "/redoc",
              lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=900)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.is_production:
    log.info("CORS origins: %s", settings.cors_origin_list)

app.include_router(datasets_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(forecasts_router, prefix="/api/v1")
@app.middleware("http")
async def response_timing(request, call_next):
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Response-Time-ms"] = f"{(perf_counter() - started) * 1000:.1f}"
    return response

@app.get("/api/v1/health")
async def health():
    # Lightweight by design: one SELECT, never Spark, never model training.
    started = perf_counter()
    db_ok = await check_db()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "latency_ms": round((perf_counter() - started) * 1000, 1)}
