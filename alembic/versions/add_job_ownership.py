from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("owner_id", sa.String(100), nullable=False, server_default="legacy"),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner_id", table_name="jobs")
    op.drop_column("jobs", "owner_id")
