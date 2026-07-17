"""
Token service tests.

Tests:
- Successful token issuance returns an opaque string
- Presented token verifies correctly against stored hash
- Replay protection: using the same token twice raises ValueError
- Expired token is rejected
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import compute_token_hash, issue_raw_token, verify_token_signature
from app.models.models import Entity, ReferenceToken
from app.services.token_service import create_token, verify_and_consume_token


# ---------------------------------------------------------------------------
# Unit tests for cryptographic primitives
# ---------------------------------------------------------------------------

def test_issue_raw_token_is_base64url():
    raw, kid, token_hash = issue_raw_token()
    # Should be decodable
    import base64
    decoded = base64.urlsafe_b64decode(raw + "==")
    assert len(decoded) > 32  # kid + "." + 32 random bytes


def test_token_hash_is_deterministic():
    raw, kid, h1 = issue_raw_token()
    _, h2 = compute_token_hash(raw)
    assert h1 == h2


def test_token_signature_verification():
    raw, kid, token_hash = issue_raw_token()
    assert verify_token_signature(raw, token_hash) is True


def test_tampered_token_fails_verification():
    raw, kid, token_hash = issue_raw_token()
    tampered = raw[:-4] + "XXXX"
    assert verify_token_signature(tampered, token_hash) is False


def test_unknown_kid_raises():
    import base64
    # Craft a token with unknown kid
    payload = b"badkid." + b"X" * 32
    raw = base64.urlsafe_b64encode(payload).decode()
    with pytest.raises(ValueError, match="Unknown signing key"):
        compute_token_hash(raw)


# ---------------------------------------------------------------------------
# Integration tests using the service layer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_token_returns_opaque_string(db_session: AsyncSession):
    entity = Entity(label="Test Entity")
    db_session.add(entity)
    await db_session.flush()

    response = await create_token(db_session, entity.id)

    assert response.token  # not empty
    assert "." not in response.token or response.token.count(".") < 3  # not a JWT
    assert response.entity_id == entity.id
    assert response.ttl_seconds > 0


@pytest.mark.asyncio
async def test_create_token_entity_not_found(db_session: AsyncSession):
    with pytest.raises(ValueError, match="not found"):
        await create_token(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_token_replay_protection(db_session: AsyncSession):
    """Using the same token twice must be rejected."""
    entity = Entity(label="Replay Test Entity")
    db_session.add(entity)
    await db_session.flush()

    # Issue token
    response = await create_token(db_session, entity.id)
    raw_token = response.token

    # First consumption should succeed
    db_token = await verify_and_consume_token(db_session, raw_token)
    assert db_token.used_at is not None

    # Second consumption must raise
    with pytest.raises(ValueError, match="already been used"):
        await verify_and_consume_token(db_session, raw_token)


@pytest.mark.asyncio
async def test_expired_token_rejected(db_session: AsyncSession):
    """Tokens past their expiry must be rejected."""
    entity = Entity(label="Expired Test Entity")
    db_session.add(entity)
    await db_session.flush()

    response = await create_token(db_session, entity.id)
    raw_token = response.token

    # Force expiry by modifying the token record directly
    from sqlalchemy import select
    from app.models.models import ReferenceToken as RT
    from app.core.security import compute_token_hash
    _, token_hash = compute_token_hash(raw_token)
    stmt = select(RT).where(RT.token_hash == token_hash)
    result = await db_session.execute(stmt)
    db_tok = result.scalar_one()
    db_tok.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    await db_session.flush()

    with pytest.raises(ValueError, match="expired"):
        await verify_and_consume_token(db_session, raw_token)
