"""SQLAlchemy ORM models for Project Vertex."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------
class Entity(Base):
    """
    A generic named entity that can participate in bidirectional links.
    In a real system this would have domain-specific fields; here it is kept
    deliberately abstract.
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    tokens: Mapped[list["ReferenceToken"]] = relationship(
        "ReferenceToken", back_populates="entity", cascade="all, delete-orphan"
    )
    links_as_a: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.entity_a_id",
        back_populates="entity_a",
    )
    links_as_b: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.entity_b_id",
        back_populates="entity_b",
    )


# ---------------------------------------------------------------------------
# ReferenceToken
# ---------------------------------------------------------------------------
class ReferenceToken(Base):
    """
    Represents a single-use, time-bound opaque reference token.

    The raw token string is NEVER stored here — only its HMAC-SHA256 hash.
    This prevents token recovery even in the event of a DB compromise.
    """

    __tablename__ = "reference_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kid: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped["Entity"] = relationship("Entity", back_populates="tokens")


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------
class Link(Base):
    """
    A bidirectional relationship between two entities.

    Bidirectionality is modeled as a single row with canonical ordering:
        entity_a_id < entity_b_id  (lexicographic UUID comparison)

    This means a single composite unique constraint covers both directions.
    The application layer enforces canonical ordering before every insert.

    ``private_notes`` is protected by PostgreSQL column-level privileges:
        REVOKE SELECT (private_notes) ON links FROM app_admin;
    """

    __tablename__ = "links"
    __table_args__ = (
        UniqueConstraint("entity_a_id", "entity_b_id", name="uq_links_pair"),
        CheckConstraint("entity_a_id != entity_b_id", name="ck_links_no_self"),
        CheckConstraint(
            "CAST(entity_a_id AS TEXT) < CAST(entity_b_id AS TEXT)",
            name="ck_links_canonical_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    entity_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    private_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity_a: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[entity_a_id], back_populates="links_as_a"
    )
    entity_b: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[entity_b_id], back_populates="links_as_b"
    )
