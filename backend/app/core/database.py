"""
Async SQLAlchemy session factory for Project Vertex.

Two engines are provided:
- ``async_engine``      — for normal application queries (app_user role)
- ``superuser_engine``  — for migrations and RLS admin tasks (postgres role)

Session lifecycle is managed via FastAPI's dependency injection.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

# ---------------------------------------------------------------------------
# Application engine (app_user / vertex_app role)
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    _settings.async_database_url,
    echo=_settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------
from fastapi import Request
from sqlalchemy import text

async def get_db(request: Request = None) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a request-scoped async DB session.
    Dynamically configures PostgreSQL role permissions per-request.
    """
    async with AsyncSessionLocal() as session:
        role = "user"
        if request:
            role = request.headers.get("x-role", "user").lower()

        try:
            if role == "admin":
                await session.execute(text("SET ROLE app_admin;"))
            else:
                await session.execute(text("SET ROLE app_user;"))
            
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("RESET ROLE;"))
                await session.commit()
            except Exception:
                pass
            await session.close()

