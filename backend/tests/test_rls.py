"""
RLS / column-privilege tests.

These tests connect directly to PostgreSQL as the app_admin role and verify
that private_notes is genuinely inaccessible — not just filtered in app code.

Tests in this file require a running PostgreSQL instance and are SKIPPED
in the normal pytest run (which uses SQLite). They are tagged with
@pytest.mark.rls and intended to be run against the real DB:

    pytest -m rls tests/test_rls.py

Prerequisites:
    - Docker Compose running: docker-compose up postgres
    - Migrations applied: alembic upgrade head
    - Roles created by 01_roles.sql init script
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

RLS_TEST_REQUIRES_POSTGRES = pytest.mark.skipif(
    os.getenv("RLS_TESTS") != "1",
    reason="RLS tests require a live PostgreSQL instance. Set RLS_TESTS=1 to enable.",
)


@RLS_TEST_REQUIRES_POSTGRES
@pytest.mark.rls
@pytest.mark.asyncio
async def test_admin_role_cannot_read_private_notes():
    """
    Connect as vertex_admin (which has the app_admin role) and attempt to
    SELECT private_notes FROM links.

    Expected: asyncpg raises InsufficientPrivilegeError because
    REVOKE SELECT (private_notes) ON links FROM app_admin was applied
    in the initial migration.
    """
    import asyncpg
    from app.core.config import get_settings

    settings = get_settings()

    # Build a DSN for the admin login role
    admin_dsn = (
        f"postgresql://vertex_admin:{settings.APP_ADMIN_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

    conn = await asyncpg.connect(admin_dsn)
    try:
        # First create a link as app_user so there's a row to query
        app_user_dsn = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        user_conn = await asyncpg.connect(app_user_dsn)
        try:
            # Insert a dummy link directly (bypass RLS via app_user role)
            a_id = str(uuid.uuid4())
            b_id = str(uuid.uuid4())
            if a_id > b_id:
                a_id, b_id = b_id, a_id

            await user_conn.execute(
                """
                INSERT INTO entities (id, label) VALUES ($1, 'RLS Test A'), ($2, 'RLS Test B')
                """,
                a_id, b_id
            )
            await user_conn.execute(
                """
                INSERT INTO links (entity_a_id, entity_b_id, private_notes)
                VALUES ($1, $2, 'TOP SECRET')
                """,
                a_id, b_id
            )
        finally:
            await user_conn.close()

        # Now try to read private_notes as admin
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT private_notes FROM links LIMIT 1")

        # But admin CAN read non-sensitive columns
        rows = await conn.fetch("SELECT id, entity_a_id, entity_b_id FROM links LIMIT 1")
        assert len(rows) >= 1

    finally:
        await conn.close()


@RLS_TEST_REQUIRES_POSTGRES
@pytest.mark.rls
@pytest.mark.asyncio
async def test_user_role_can_read_private_notes():
    """
    Verify that the app_user role CAN read private_notes (for contrast).
    """
    import asyncpg
    from app.core.config import get_settings

    settings = get_settings()

    app_user_dsn = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

    conn = await asyncpg.connect(app_user_dsn)
    try:
        rows = await conn.fetch("SELECT private_notes FROM links LIMIT 1")
        # Just checking the query executes without error
        assert isinstance(rows, list)
    finally:
        await conn.close()
