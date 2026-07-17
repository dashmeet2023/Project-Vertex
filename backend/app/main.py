"""FastAPI application entry point for Project Vertex."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import entities as entities_router
from app.api import state as state_router
from app.core.config import get_settings
from app.core.database import async_engine
from app.schemas.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title="Project Vertex",
    description=(
        "Atomic State Sync Engine — bidirectional entity linking "
        "with signed opaque tokens, RLS-protected metadata, and cursor pagination."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Role"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(state_router.router)
app.include_router(entities_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Liveness + DB connectivity check."""
    db_status = "ok"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(status="ok", db=db_status)


# ---------------------------------------------------------------------------
# Global exception handler (prevents leaking stack traces)
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
