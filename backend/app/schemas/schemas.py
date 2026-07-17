"""
Pydantic v2 schemas for Project Vertex API.

Separation of concerns:
- *Request* schemas validate incoming payloads.
- *Response* schemas define what the API returns (never expose raw_token hashes).
- *Cursor* schemas handle encoded pagination state.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class VertexBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class EntityCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class EntityResponse(VertexBase):
    id: uuid.UUID
    label: str
    owner_role: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Reference Token
# ---------------------------------------------------------------------------

class TokenIssueRequest(BaseModel):
    entity_id: uuid.UUID


class TokenIssueResponse(BaseModel):
    """
    Returns the raw_token to the caller.
    The token_hash is NEVER exposed in any response.
    """
    token: str        # opaque raw token — client treats this as a black box
    entity_id: uuid.UUID
    expires_at: datetime
    ttl_seconds: int


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    """
    Consume a reference token to link its entity with a second entity.

    The reference token identifies entity A; entity_b_id is supplied explicitly.
    """
    token: str = Field(..., description="Opaque reference token from POST /api/state/tokens")
    entity_b_id: uuid.UUID = Field(..., description="UUID of the second entity to link")
    private_notes: str | None = Field(
        None,
        max_length=2000,
        description="Optional private notes — only visible to app_user role, not app_admin",
    )


class LinkResponse(VertexBase):
    """
    A confirmed bidirectional link resource.

    Note: private_notes is conditionally included; when the request is made
    with the admin role, it will be absent/null (enforced at DB layer).
    """
    id: uuid.UUID
    entity_a_id: uuid.UUID
    entity_b_id: uuid.UUID
    private_notes: str | None = None
    created_at: datetime
    entity_a: EntityResponse | None = None
    entity_b: EntityResponse | None = None


# ---------------------------------------------------------------------------
# Cursor-based pagination
# ---------------------------------------------------------------------------

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """Generic wrapper for a single cursor-paginated page."""
    items: list[T]
    next_cursor: str | None = None
    total_returned: int

    model_config = ConfigDict(arbitrary_types_allowed=True)


def encode_cursor(created_at: datetime, id: uuid.UUID) -> str:
    """Encode (created_at, id) into an opaque, URL-safe base64 cursor string."""
    raw = json.dumps({"t": created_at.isoformat(), "i": str(id)})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a cursor string back into (created_at, id)."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"==").decode()
        data = json.loads(raw)
        return datetime.fromisoformat(data["t"]), uuid.UUID(data["i"])
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    db: str = "ok"
