from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None

def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("course", sa.String(200), nullable=False),
        sa.Column("org", sa.String(200), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "completed",
                "completed_with_errors",
                "failed",
                name="job_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "recipients",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("row", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("number", sa.String(100)),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="item_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "row"),
    )
    op.create_index("ix_recipients_job_id", "recipients", ["job_id"])
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("recipient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recipient_id"),
    )

def downgrade() -> None:
    op.drop_table("certificates")
    op.drop_index("ix_recipients_job_id", table_name="recipients")
    op.drop_table("recipients")
    op.drop_table("jobs")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE item_status")
        op.execute("DROP TYPE job_status")
