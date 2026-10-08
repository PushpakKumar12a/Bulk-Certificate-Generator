from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("owner", sa.String(200), nullable=False, server_default="legacy"),
    )
    op.create_index("ix_jobs_owner", "jobs", ["owner"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner", table_name="jobs")
    op.drop_column("jobs", "owner")
