"""FastAPI entrypoint. REST only; browser receives aggregates, never raw rows."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.datasets import router as datasets_router
from app.api.forecasts import router as forecasts_router
from app.core.config import get_settings
from app.db.session import check_db

log = logging.getLogger("retail-intelligence")
settings = get_settings()

app = FastAPI(title="Retail Intelligence API", version="0.1.0",
              docs_url=None if settings.is_production else "/docs",
              redoc_url=None if settings.is_production else "/redoc")

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


@app.get("/api/v1/health")
async def health():
    # Lightweight by design: one SELECT, never Spark, never model training.
    db_ok = await check_db()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
