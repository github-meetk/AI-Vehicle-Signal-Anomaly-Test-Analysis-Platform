"""FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import anomalies, dashboard, investigations, requirements, scenarios, signals, tests
from app.core.config import settings
from app.core.logging import setup_logging
from app.database.models import init_db
from app.services.scenario_service import ScenarioService
from app.database.models import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    db = SessionLocal()
    try:
        svc = ScenarioService(db)
        svc.seed_signal_definitions()
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI Vehicle Signal Anomaly & Test Analysis Platform",
    description=(
        "Deterministic anomaly detection with AI-assisted investigation "
        "for E/E battery/thermal signal data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router, prefix="/api", tags=["signals"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(anomalies.router, prefix="/api", tags=["anomalies"])
app.include_router(investigations.router, prefix="/api", tags=["investigations"])
app.include_router(requirements.router, prefix="/api", tags=["requirements"])
app.include_router(tests.router, prefix="/api", tags=["tests"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])


@app.get("/health")
def health():
    return {"status": "healthy", "env": settings.app_env}
