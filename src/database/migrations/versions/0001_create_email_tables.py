"""Create emails and attachments tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_create_email_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("sender_email", sa.String(), nullable=False),
        sa.Column("sender_name", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("body_content", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("folder_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_emails_sender", "emails", ["sender_email"])
    op.create_index("idx_emails_received", "emails", ["received_at"])
    op.create_index("idx_emails_folder", "emails", ["folder_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email_id", sa.String(), sa.ForeignKey("emails.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("local_path", sa.String(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_attachments_email", "attachments", ["email_id"])


def downgrade() -> None:
    op.drop_index("idx_attachments_email", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("idx_emails_folder", table_name="emails")
    op.drop_index("idx_emails_received", table_name="emails")
    op.drop_index("idx_emails_sender", table_name="emails")
    op.drop_table("emails")
