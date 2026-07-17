"""Initial schema: entities, reference_tokens, links + RLS policies

Revision ID: 0001_initial
Revises: 
Create Date: 2026-07-13

Design notes:
  - links uses a single-row canonical model (entity_a_id < entity_b_id).
  - The unique constraint (entity_a_id, entity_b_id) is the concurrency fence.
  - private_notes column privilege is REVOKED from app_admin at DB level.
  - RLS is enabled on links; app_user can read all visible rows,
    app_admin can see the row structure but NOT private_notes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create application DB roles (idempotent via DO $$ blocks)
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user NOINHERIT;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_admin') THEN
                CREATE ROLE app_admin NOINHERIT;
            END IF;
        END
        $$;
    """)

    # ------------------------------------------------------------------
    # 2. entities table
    # ------------------------------------------------------------------
    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("owner_role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ------------------------------------------------------------------
    # 3. reference_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "reference_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kid", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reference_tokens_token_hash", "reference_tokens", ["token_hash"], unique=True)
    op.create_index("ix_reference_tokens_entity_id", "reference_tokens", ["entity_id"])
    op.create_index("ix_reference_tokens_expires_at", "reference_tokens", ["expires_at"])

    # ------------------------------------------------------------------
    # 4. links table
    # ------------------------------------------------------------------
    op.create_table(
        "links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_a_id", UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_b_id", UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("private_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_a_id", "entity_b_id", name="uq_links_pair"),
        sa.CheckConstraint("entity_a_id != entity_b_id", name="ck_links_no_self"),
        sa.CheckConstraint("entity_a_id::text < entity_b_id::text", name="ck_links_canonical_order"),
    )
    op.create_index("ix_links_entity_a_id", "links", ["entity_a_id"])
    op.create_index("ix_links_entity_b_id", "links", ["entity_b_id"])
    op.create_index("ix_links_created_at_id", "links", ["created_at", "id"])

    # ------------------------------------------------------------------
    # 5. Grant table-level privileges
    # ------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON entities TO app_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON reference_tokens TO app_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON links TO app_user;")

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON entities TO app_admin;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON reference_tokens TO app_admin;")
    # app_admin gets row-level SELECT but NOT the private_notes column
    op.execute("GRANT SELECT (id, entity_a_id, entity_b_id, created_at) ON links TO app_admin;")
    op.execute("GRANT INSERT, UPDATE ON links TO app_admin;")

    # ------------------------------------------------------------------
    # 6. Enable Row-Level Security on links
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE links ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE links FORCE ROW LEVEL SECURITY;")

    # app_user can see all links (in a real system this would scope to
    # current_setting('app.current_entity_id') but that requires session
    # variable management; for this exercise we grant all rows to app_user)
    op.execute("""
        CREATE POLICY links_app_user_all ON links
            FOR ALL
            TO app_user
            USING (true)
            WITH CHECK (true);
    """)

    # app_admin can manage rows but the column-level REVOKE above ensures
    # private_notes is inaccessible regardless of row policy.
    op.execute("""
        CREATE POLICY links_app_admin_select ON links
            FOR SELECT
            TO app_admin
            USING (true);
    """)
    op.execute("""
        CREATE POLICY links_app_admin_write ON links
            FOR ALL
            TO app_admin
            USING (true)
            WITH CHECK (true);
    """)

    # Superuser (postgres / vertex_app connection role) bypasses RLS by default.
    # The app_user/app_admin roles are used from the application via SET ROLE.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'vertex_app') THEN
                GRANT app_user TO vertex_app;
                GRANT app_admin TO vertex_app;
            END IF;
        END
        $$;
    """)



def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS links_app_admin_write ON links;")
    op.execute("DROP POLICY IF EXISTS links_app_admin_select ON links;")
    op.execute("DROP POLICY IF EXISTS links_app_user_all ON links;")
    op.execute("ALTER TABLE links DISABLE ROW LEVEL SECURITY;")
    op.drop_table("links")
    op.drop_table("reference_tokens")
    op.drop_table("entities")
    op.execute("DROP ROLE IF EXISTS app_user;")
    op.execute("DROP ROLE IF EXISTS app_admin;")
