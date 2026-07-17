"""
Entity router — create and list entities.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.schemas import EntityCreate, EntityResponse
from app.services import entity_service

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.post(
    "",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new entity",
)
async def create_entity(
    body: EntityCreate,
    db: AsyncSession = Depends(get_db),
) -> EntityResponse:
    return await entity_service.create_entity(db, body)


@router.get(
    "",
    response_model=list[EntityResponse],
    summary="List entities (newest first, max 50)",
)
async def list_entities(
    db: AsyncSession = Depends(get_db),
) -> list[EntityResponse]:
    return await entity_service.list_entities(db)


@router.get(
    "/{entity_id}",
    response_model=EntityResponse,
    summary="Get a single entity by ID",
)
async def get_entity(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EntityResponse:
    entity = await entity_service.get_entity(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity
