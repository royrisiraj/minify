"""Add durable, case-sensitive short links."""

import sqlalchemy as sa
from alembic import op

revision = "0002_links"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("short_code", sa.String(7, collation="C"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code", name="uq_links_short_code"),
        sa.CheckConstraint("short_code ~ '^[0-9A-Za-z]{7}$'", name="ck_links_short_code_base62"),
    )


def downgrade() -> None:
    op.drop_table("links")
