"""claude_code_history

Revision ID: 20260325_claude_code_history
Revises: 20260322_llm_fallback_tracking
"""

from alembic import op
import sqlalchemy as sa

revision = "20260325_claude_code_history"
down_revision = "20260322_llm_fallback_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claude_code_sync_cursor",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("project_path", sa.Text, nullable=False),
        sa.Column("entry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_mtime", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "session_id", name="uq_cc_cursor_user_session"),
    )
    op.create_index("ix_cc_cursor_user_id", "claude_code_sync_cursor", ["user_id"])

    op.create_table(
        "project_activity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id"), nullable=False),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("source_project_path", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "session_id", name="uq_project_activity_user_session"),
    )
    op.create_index("ix_project_activity_user_id", "project_activity", ["user_id"])
    op.create_index(
        "ix_project_activity_user_project_date",
        "project_activity",
        ["user_id", "project_id", "local_date"],
    )

    op.add_column("project", sa.Column("state_summary_json", sa.JSON, nullable=True))
    op.add_column("project", sa.Column("state_updated_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("journal_entry", sa.Column("source", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("journal_entry", "source")
    op.drop_column("project", "state_updated_at_utc")
    op.drop_column("project", "state_summary_json")
    op.drop_index("ix_project_activity_user_project_date", table_name="project_activity")
    op.drop_index("ix_project_activity_user_id", table_name="project_activity")
    op.drop_table("project_activity")
    op.drop_index("ix_cc_cursor_user_id", table_name="claude_code_sync_cursor")
    op.drop_table("claude_code_sync_cursor")
