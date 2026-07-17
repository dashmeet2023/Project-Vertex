"""
Entity CRUD service.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Entity
from app.schemas.schemas import EntityCreate, EntityResponse


async def create_entity(session: AsyncSession, data: EntityCreate) -> EntityResponse:
    entity = Entity(label=data.label)
    session.add(entity)
    await session.flush()
    await session.refresh(entity)
    return EntityResponse.model_validate(entity)


async def list_entities(session: AsyncSession, limit: int = 50) -> list[EntityResponse]:
    stmt = select(Entity).order_by(Entity.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [EntityResponse.model_validate(e) for e in result.scalars().all()]


async def get_entity(session: AsyncSession, entity_id: uuid.UUID) -> EntityResponse | None:
    entity = await session.get(Entity, entity_id)
    if entity is None:
        return None
    return EntityResponse.model_validate(entity)
