"""
Pagination correctness tests.

Validates that cursor-based traversal of N links returns every link
exactly once, in a stable order, with no duplicates or omissions.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Entity, Link


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


async def _create_links(session: AsyncSession, n: int) -> list[uuid.UUID]:
    """Create n entities and n/2 links between consecutive pairs."""
    entities = [Entity(label=f"Paginate Entity {i}") for i in range(n)]
    session.add_all(entities)
    await session.flush()

    link_ids = []
    created_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for i in range(0, len(entities) - 1, 2):
        a, b = entities[i].id, entities[i + 1].id
        ca, cb = _canonical_pair(a, b)
        if (ca, cb) in created_pairs:
            continue
        created_pairs.add((ca, cb))
        link = Link(entity_a_id=ca, entity_b_id=cb)
        session.add(link)
        await session.flush()
        link_ids.append(link.id)

    await session.commit()
    return link_ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagination_single_page(client: AsyncClient, db_session: AsyncSession):
    """Fewer items than page size → next_cursor is null."""
    await _create_links(db_session, 4)  # 2 links

    resp = await client.get("/api/state/links", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_cursor"] is None
    assert data["total_returned"] == len(data["items"])


@pytest.mark.asyncio
async def test_pagination_full_traversal_no_duplicates(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Create 25 links, paginate with limit=10.
    Should produce 3 pages: 10 + 10 + 5, with no duplicate IDs.
    """
    total_links = 25
    # Need 50 entities for 25 distinct pairs
    entities = [Entity(label=f"Pag Entity {i}") for i in range(50)]
    db_session.add_all(entities)
    await db_session.flush()

    created_pairs: set[tuple[str, str]] = set()
    links_created = 0
    for i in range(0, 50 - 1, 2):
        if links_created >= total_links:
            break
        a_id = str(entities[i].id)
        b_id = str(entities[i + 1].id)
        ca, cb = (a_id, b_id) if a_id < b_id else (b_id, a_id)
        if (ca, cb) in created_pairs:
            continue
        created_pairs.add((ca, cb))
        link = Link(
            entity_a_id=uuid.UUID(ca),
            entity_b_id=uuid.UUID(cb),
        )
        db_session.add(link)
        await db_session.flush()
        links_created += 1

    await db_session.commit()

    # Traverse all pages
    all_ids: list[str] = []
    cursor: str | None = None
    page_sizes: list[int] = []

    while True:
        params: dict = {"limit": 10}
        if cursor:
            params["cursor"] = cursor

        resp = await client.get("/api/state/links", params=params)
        assert resp.status_code == 200
        data = resp.json()

        page_ids = [item["id"] for item in data["items"]]
        all_ids.extend(page_ids)
        page_sizes.append(len(page_ids))

        cursor = data.get("next_cursor")
        if cursor is None:
            break

    # All IDs must be unique (no duplicates)
    assert len(all_ids) == len(set(all_ids)), "Duplicate IDs found across pages!"

    # Must have retrieved all created links
    assert len(all_ids) == links_created, (
        f"Expected {links_created} total, got {len(all_ids)}"
    )

    # Page sizes must be non-zero and ≤ limit
    assert all(0 < s <= 10 for s in page_sizes)


@pytest.mark.asyncio
async def test_pagination_invalid_cursor_returns_400(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/state/links", params={"cursor": "not_a_valid_cursor"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_pagination_limit_clamped(client: AsyncClient, db_session: AsyncSession):
    """Requesting limit > 100 should be rejected by query param validation."""
    resp = await client.get("/api/state/links", params={"limit": 999})
    assert resp.status_code == 422  # FastAPI query validation
