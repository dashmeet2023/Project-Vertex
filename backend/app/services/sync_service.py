"""
Sync service — the heart of Project Vertex.

Atomically:
  1. Verifies and consumes the reference token (marks used_at).
  2. Resolves the referenced entity (entity A).
  3. Creates a canonical bidirectional link between entity A and entity B.

Concurrency safety:
  - The ``links`` table has a UNIQUE constraint on (entity_a_id, entity_b_id).
  - Canonical ordering (smaller UUID text < larger) is enforced before insert.
  - We use INSERT ... ON CONFLICT DO NOTHING + SELECT fallback for idempotency.
  - Token consumption uses SELECT FOR UPDATE (in token_service) preventing
    two concurrent requests from both passing the single-use check.

All of the above happens within ONE database transaction.
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.models.models import Entity, Link
from app.schemas.schemas import LinkResponse
from app.services.token_service import verify_and_consume_token


def _canonical_pair(id_a: uuid.UUID, id_b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """
    Enforce canonical ordering so both (A,B) and (B,A) map to the same row.
    Comparison is on the string representation of the UUID (lexicographic).
    """
    if str(id_a) < str(id_b):
        return id_a, id_b
    return id_b, id_a


async def sync_entities(
    session: AsyncSession,
    raw_token: str,
    entity_b_id: uuid.UUID,
    private_notes: str | None = None,
    role: str = "user",
) -> tuple[LinkResponse, bool]:
    """
    Consume ``raw_token`` and create (or retrieve) the bidirectional link.

    Returns:
        (link_response, created)
        - created=True  → 201 Created
        - created=False → 200 OK (idempotent duplicate)

    All work happens in the caller's transaction; the caller is responsible
    for commit/rollback.
    """
    # ── Step 1: Verify & consume token (row-locked) ──────────────────────────
    db_token = await verify_and_consume_token(session, raw_token)
    entity_a_id = db_token.entity_id

    # ── Step 2: Validate both entities exist ─────────────────────────────────
    entity_a = await session.get(Entity, entity_a_id)
    entity_b = await session.get(Entity, entity_b_id)

    if entity_a is None:
        raise ValueError(f"Entity A ({entity_a_id}) not found")
    if entity_b is None:
        raise ValueError(f"Entity B ({entity_b_id}) not found")
    if entity_a_id == entity_b_id:
        raise ValueError("Cannot link an entity to itself")

    # ── Step 3: Canonical ordering ────────────────────────────────────────────
    canonical_a, canonical_b = _canonical_pair(entity_a_id, entity_b_id)

    # ── Step 4: INSERT ON CONFLICT DO NOTHING ────────────────────────────────
    # We use raw SQL here to leverage ON CONFLICT DO NOTHING cleanly.
    # SQLAlchemy 2.x insert().on_conflict_do_nothing() works too but the
    # raw approach makes the intent explicit.
    new_id = uuid.uuid4()
    insert_sql = text(
        """
        INSERT INTO links (id, entity_a_id, entity_b_id, private_notes)
        VALUES (:id, :a_id, :b_id, :notes)
        ON CONFLICT (entity_a_id, entity_b_id) DO NOTHING
        RETURNING id
        """
    )
    result = await session.execute(
        insert_sql,
        {
            "id": new_id,
            "a_id": canonical_a,
            "b_id": canonical_b,
            "notes": private_notes,
        },
    )
    returned_id = result.scalar_one_or_none()
    created = returned_id is not None

    # ── Step 5: Fetch the (new or existing) link ──────────────────────────────
    options = [defer(Link.private_notes)] if role == "admin" else []
    
    if created:
        link = await session.get(Link, new_id, options=options)
    else:
        # ON CONFLICT path — fetch existing row
        fetch_sql = text(
            "SELECT id FROM links WHERE entity_a_id = :a_id AND entity_b_id = :b_id"
        )
        res = await session.execute(
            fetch_sql, {"a_id": canonical_a, "b_id": canonical_b}
        )
        existing_id = res.scalar_one()
        link = await session.get(Link, existing_id, options=options)

    # Eagerly load relationships for the response
    await session.refresh(link, ["entity_a", "entity_b"])

    response = LinkResponse(
        id=link.id,
        entity_a_id=link.entity_a_id,
        entity_b_id=link.entity_b_id,
        private_notes=None if role == "admin" else link.private_notes,
        created_at=link.created_at,
        entity_a=link.entity_a,
        entity_b=link.entity_b,
    )

    return response, created
