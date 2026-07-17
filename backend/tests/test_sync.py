"""
Sync endpoint concurrency tests.

Key test: 20 concurrent POST /api/state/sync requests for the same entity pair
must result in exactly ONE link being created (idempotent, no duplicates).

This validates both the UNIQUE constraint + ON CONFLICT strategy and the
single-use token replay protection under concurrent load.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Entity, Link, ReferenceToken
from app.services.token_service import create_token


# ---------------------------------------------------------------------------
# Helper: create entity + token via service layer
# ---------------------------------------------------------------------------

async def _create_entity_with_token(session: AsyncSession, label: str) -> tuple[Entity, str]:
    entity = Entity(label=label)
    session.add(entity)
    await session.flush()
    response = await create_token(session, entity.id)
    return entity, response.token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_creates_link(client: AsyncClient, db_session: AsyncSession):
    """Basic: a single sync request creates a link and returns 201."""
    entity_a = Entity(label="Sync Source")
    entity_b = Entity(label="Sync Target")
    db_session.add_all([entity_a, entity_b])
    await db_session.flush()

    tok_response = await create_token(db_session, entity_a.id)
    await db_session.commit()

    resp = await client.post("/api/state/sync", json={
        "token": tok_response.token,
        "entity_b_id": str(entity_b.id),
        "private_notes": "test note",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_sync_idempotent_returns_200(client: AsyncClient, db_session: AsyncSession):
    """When link already exists (via a second token), return 200 not 201."""
    entity_a = Entity(label="Idempotent Source")
    entity_b = Entity(label="Idempotent Target")
    db_session.add_all([entity_a, entity_b])
    await db_session.flush()

    # Issue two separate tokens for entity_a
    tok1 = await create_token(db_session, entity_a.id)
    tok2 = await create_token(db_session, entity_a.id)
    await db_session.commit()

    # First sync → creates link (201)
    r1 = await client.post("/api/state/sync", json={
        "token": tok1.token,
        "entity_b_id": str(entity_b.id),
    })
    assert r1.status_code == 201

    # Second sync → link already exists (200)
    r2 = await client.post("/api/state/sync", json={
        "token": tok2.token,
        "entity_b_id": str(entity_b.id),
    })
    assert r2.status_code == 200
    assert r2.json()["created"] is False


@pytest.mark.asyncio
async def test_sync_replay_token_rejected(client: AsyncClient, db_session: AsyncSession):
    """Reusing the same token must return 409 Conflict."""
    entity_a = Entity(label="Replay Source")
    entity_b = Entity(label="Replay Target")
    db_session.add_all([entity_a, entity_b])
    await db_session.flush()

    tok = await create_token(db_session, entity_a.id)
    await db_session.commit()

    r1 = await client.post("/api/state/sync", json={
        "token": tok.token,
        "entity_b_id": str(entity_b.id),
    })
    assert r1.status_code == 201

    r2 = await client.post("/api/state/sync", json={
        "token": tok.token,  # same token!
        "entity_b_id": str(entity_b.id),
    })
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_sync_self_link_rejected(client: AsyncClient, db_session: AsyncSession):
    """Linking an entity to itself must be rejected."""
    entity = Entity(label="Self Link")
    db_session.add(entity)
    await db_session.flush()
    tok = await create_token(db_session, entity.id)
    await db_session.commit()

    resp = await client.post("/api/state/sync", json={
        "token": tok.token,
        "entity_b_id": str(entity.id),
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sync_concurrency_exactly_one_link(
    client: AsyncClient, db_session: AsyncSession
):
    """
    CRITICAL CONCURRENCY TEST

    Issue 20 separate tokens for entity_a (each token can only be used once),
    then fire all 20 sync requests concurrently.

    Expected outcome:
    - Exactly 1 link row exists in the database.
    - 1 request gets 201 (first to commit).
    - 19 requests get 200 (ON CONFLICT → idempotent existing link).
    - 0 duplicates.

    This validates the UNIQUE constraint + ON CONFLICT DO NOTHING strategy
    under concurrent load without deadlocks.
    """
    N = 20

    entity_a = Entity(label="Concurrent Source")
    entity_b = Entity(label="Concurrent Target")
    db_session.add_all([entity_a, entity_b])
    await db_session.flush()

    # Issue N tokens (each single-use)
    tokens = []
    for i in range(N):
        tok = await create_token(db_session, entity_a.id)
        tokens.append(tok.token)

    await db_session.commit()

    # Fire all N syncs concurrently
    async def do_sync(token: str) -> int:
        resp = await client.post("/api/state/sync", json={
            "token": token,
            "entity_b_id": str(entity_b.id),
        })
        return resp.status_code

    status_codes = await asyncio.gather(*[do_sync(t) for t in tokens])

    # All requests should succeed (201 or 200)
    assert all(s in (200, 201) for s in status_codes), f"Unexpected statuses: {status_codes}"

    # Exactly one 201 (the winner) and N-1 200s (idempotent)
    created_count = status_codes.count(201)
    assert created_count == 1, f"Expected 1 creation, got {created_count}: {status_codes}"

    # DB must have exactly 1 link for this pair
    from sqlalchemy import text
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM links WHERE "
             "(entity_a_id = :a AND entity_b_id = :b) OR "
             "(entity_a_id = :b AND entity_b_id = :a)"),
        {"a": str(entity_a.id), "b": str(entity_b.id)},
    )
    count = result.scalar_one()
    assert count == 1, f"Expected exactly 1 link in DB, found {count}"
