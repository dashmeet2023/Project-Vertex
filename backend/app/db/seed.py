#!/usr/bin/env python3
"""
Seed script: creates a few example entities for local development.

Usage:
    cd backend
    python -m app.db.seed

Requires the DB to be running and migrations to be applied.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.models import Entity

SEED_ENTITIES = [
    {"label": "Alpha Node", "owner_role": "user"},
    {"label": "Beta Node", "owner_role": "user"},
    {"label": "Gamma Node", "owner_role": "user"},
    {"label": "Delta Node", "owner_role": "user"},
    {"label": "Epsilon Node", "owner_role": "admin"},
]


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=True)
    AsyncSession_ = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSession_() as session:
        async with session.begin():
            for data in SEED_ENTITIES:
                entity = Entity(**data)
                session.add(entity)
        print(f"Seeded {len(SEED_ENTITIES)} entities.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
