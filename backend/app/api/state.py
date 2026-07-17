"""
State router — tokens, sync, and links directory.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.schemas import (
    CursorPage,
    LinkResponse,
    SyncRequest,
    TokenIssueRequest,
    TokenIssueResponse,
)
from app.services import entity_service, link_service, sync_service, token_service

router = APIRouter(prefix="/api/state", tags=["state"])


# ---------------------------------------------------------------------------
# Token issuance
# ---------------------------------------------------------------------------

@router.post(
    "/tokens",
    response_model=TokenIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an opaque reference token for an entity",
)
async def issue_token(
    body: TokenIssueRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenIssueResponse:
    try:
        return await token_service.create_token(db, body.entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Sync (atomic bidirectional link creation)
# ---------------------------------------------------------------------------

@router.post(
    "/sync",
    summary="Consume a reference token and atomically create a bidirectional link",
    status_code=status.HTTP_201_CREATED,
)
async def sync(
    request: Request,
    body: SyncRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        role = request.headers.get("x-role", "user").lower()
        link, created = await sync_service.sync_entities(
            session=db,
            raw_token=body.token,
            entity_b_id=body.entity_b_id,
            private_notes=body.private_notes,
            role=role,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already been used" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        if "expired" in msg:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    # FastAPI doesn't support dynamic status codes via return easily,
    # so we return the response data and let the caller inspect the `created` flag.
    # The response body includes a `created` boolean so clients know which path was taken.
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={
            "id": str(link.id),
            "entity_a_id": str(link.entity_a_id),
            "entity_b_id": str(link.entity_b_id),
            "private_notes": link.private_notes,
            "created_at": link.created_at.isoformat(),
            "created": created,
            "entity_a": {
                "id": str(link.entity_a.id),
                "label": link.entity_a.label,
                "owner_role": link.entity_a.owner_role,
                "created_at": link.entity_a.created_at.isoformat(),
            } if link.entity_a else None,
            "entity_b": {
                "id": str(link.entity_b.id),
                "label": link.entity_b.label,
                "owner_role": link.entity_b.owner_role,
                "created_at": link.entity_b.created_at.isoformat(),
            } if link.entity_b else None,
        },
        status_code=http_status,
    )


# ---------------------------------------------------------------------------
# Links directory (cursor-paginated)
# ---------------------------------------------------------------------------

@router.get(
    "/links",
    response_model=CursorPage[LinkResponse],
    summary="List links with cursor-based pagination",
)
async def list_links(
    request: Request,
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: AsyncSession = Depends(get_db),
) -> CursorPage[LinkResponse]:
    try:
        role = request.headers.get("x-role", "user").lower()
        return await link_service.list_links(db, cursor=cursor, limit=limit, role=role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

