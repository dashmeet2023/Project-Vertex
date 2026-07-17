"""
Link listing service with cursor-based (keyset) pagination.

Cursor encoding:
    opaque base64url of JSON { "t": ISO-8601 timestamp, "i": UUID string }

Keyset query:
    WHERE (created_at, id) < (cursor_created_at, cursor_id)
    ORDER BY created_at DESC, id DESC
    LIMIT n

This gives stable pagination even when new rows are concurrently inserted
between pages, unlike offset/limit which can skip or duplicate rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, defer

from app.models.models import Link
from app.schemas.schemas import CursorPage, LinkResponse, decode_cursor, encode_cursor

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


async def list_links(
    session: AsyncSession,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    role: str = "user",
) -> CursorPage[LinkResponse]:
    """
    Return a cursor-paginated page of links, newest first.
    """
    limit = min(max(1, limit), MAX_PAGE_SIZE)

    stmt = (
        select(Link)
        .options(selectinload(Link.entity_a), selectinload(Link.entity_b))
        .order_by(Link.created_at.desc(), Link.id.desc())
        .limit(limit + 1)  # fetch one extra to determine if there's a next page
    )

    if role == "admin":
        stmt = stmt.options(defer(Link.private_notes))

    if cursor:
        try:
            cursor_created_at, cursor_id = decode_cursor(cursor)
        except ValueError as exc:
            raise ValueError(f"Invalid cursor: {exc}") from exc

        # Keyset condition: (created_at, id) < (cursor_created_at, cursor_id)
        # Using DESC order, "before cursor" means:
        #   created_at < cursor_created_at
        #   OR (created_at == cursor_created_at AND id < cursor_id)
        stmt = stmt.where(
            or_(
                Link.created_at < cursor_created_at,
                and_(
                    Link.created_at == cursor_created_at,
                    Link.id < cursor_id,
                ),
            )
        )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    link_responses = [
        LinkResponse(
            id=link.id,
            entity_a_id=link.entity_a_id,
            entity_b_id=link.entity_b_id,
            private_notes=None if role == "admin" else link.private_notes,
            created_at=link.created_at,
            entity_a=link.entity_a,
            entity_b=link.entity_b,
        )
        for link in items
    ]

    return CursorPage(
        items=link_responses,
        next_cursor=next_cursor,
        total_returned=len(link_responses),
    )

