"""job_run

Adds the job_run table: one row per job name holding durable throttle/state
for Lambda-safe background job controllers.

Revision ID: 20260604_job_run
Revises: 20260604_garmin_token_store
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_job_run"
down_revision = "20260604_garmin_token_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "job_run" not in tables:
        op.create_table(
            "job_run",
            sa.Column("job_name", sa.String, primary_key=True),
            sa.Column("running", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_allowed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    op.drop_table("job_run")
