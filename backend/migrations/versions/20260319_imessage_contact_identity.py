"""Add cached iMessage contact identity table.

Revision ID: 20260319_imessage_contact_identity
Revises: 20260318_imessage_action_source_attribution
Create Date: 2026-03-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_imessage_contact_identity"
down_revision = "20260318_imessage_action_source_attribution"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "imessage_contact_identity" not in table_names:
        op.create_table(
            "imessage_contact_identity",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("identifier", sa.String(length=255), nullable=False),
            sa.Column("normalized_identifier", sa.String(length=255), nullable=True),
            sa.Column("identifier_kind", sa.String(length=32), nullable=True),
            sa.Column("resolved_name", sa.String(length=255), nullable=True),
            sa.Column("source_record_id", sa.String(length=255), nullable=True),
            sa.Column("last_resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "identifier",
                name="uq_imessage_contact_identity_user_identifier",
            ),
        )
        op.create_index(
            "ix_imessage_contact_identity_user_id",
            "imessage_contact_identity",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "ix_imessage_contact_identity_normalized_identifier",
            "imessage_contact_identity",
            ["normalized_identifier"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "imessage_contact_identity" in table_names:
        op.drop_index(
            "ix_imessage_contact_identity_normalized_identifier",
            table_name="imessage_contact_identity",
        )
        op.drop_index(
            "ix_imessage_contact_identity_user_id",
            table_name="imessage_contact_identity",
        )
        op.drop_table("imessage_contact_identity")
