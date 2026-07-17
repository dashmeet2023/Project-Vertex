"""
Token issuance and verification service for Project Vertex.

Responsibilities:
- Issue a new opaque reference token for a given entity.
- Verify a presented raw_token (signature + expiry + single-use).
- Mark a token as consumed atomically.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import compute_token_hash, issue_raw_token, verify_token_signature
from app.models.models import Entity, ReferenceToken
from app.schemas.schemas import TokenIssueResponse


async def create_token(session: AsyncSession, entity_id: str) -> TokenIssueResponse:
    """
    Issue a new opaque reference token for the given entity.

    The raw token is returned once and never stored; only the HMAC hash
    is persisted in the database.
    """
    settings = get_settings()

    # Verify entity exists
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise ValueError(f"Entity {entity_id!r} not found")

    # Generate token
    raw_token, kid, token_hash = issue_raw_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.TOKEN_TTL_SECONDS)

    db_token = ReferenceToken(
        kid=kid,
        token_hash=token_hash,
        entity_id=entity.id,
        expires_at=expires_at,
    )
    session.add(db_token)
    await session.flush()

    return TokenIssueResponse(
        token=raw_token,
        entity_id=entity.id,
        expires_at=expires_at,
        ttl_seconds=settings.TOKEN_TTL_SECONDS,
    )


async def verify_and_consume_token(
    session: AsyncSession, raw_token: str
) -> ReferenceToken:
    """
    Verify a raw token and atomically mark it as consumed.

    This is called inside the sync transaction so that token consumption
    and link creation are atomic — preventing replay across concurrent requests.

    Raises:
        ValueError with a descriptive message on any verification failure.
    """
    # Step 1: Derive hash (also validates structure / kid)
    try:
        kid, token_hash = compute_token_hash(raw_token)
    except ValueError as exc:
        raise ValueError(f"Invalid token format: {exc}") from exc

    # Step 2: Fetch token record
    stmt = (
        select(ReferenceToken)
        .where(ReferenceToken.token_hash == token_hash)
        .with_for_update()  # row-lock during consumption
    )
    result = await session.execute(stmt)
    db_token: ReferenceToken | None = result.scalar_one_or_none()

    if db_token is None:
        raise ValueError("Token not found")

    # Step 3: Signature check (redundant but defense-in-depth)
    if not verify_token_signature(raw_token, db_token.token_hash):
        raise ValueError("Token signature invalid")

    # Step 4: Expiry
    now = datetime.now(timezone.utc)
    if db_token.expires_at < now:
        raise ValueError("Token has expired")

    # Step 5: Single-use (replay protection)
    if db_token.used_at is not None:
        raise ValueError("Token has already been used (replay rejected)")

    # Step 6: Mark consumed (within the same transaction)
    db_token.used_at = now
    await session.flush()

    return db_token
