"""add generated reels table

Revision ID: c9a8f0f8d2b1
Revises: b032c85c242c
Create Date: 2026-03-14 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9a8f0f8d2b1"
down_revision: Union[str, Sequence[str], None] = "b032c85c242c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "generated_reels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("artifact_dir", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="topic", nullable=False),
        sa.Column("script_word_count", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("topic_generated_at", sa.DateTime(), nullable=True),
        sa.Column("script_generated_at", sa.DateTime(), nullable=True),
        sa.Column("voice_generated_at", sa.DateTime(), nullable=True),
        sa.Column("visuals_generated_at", sa.DateTime(), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_reels_id"), "generated_reels", ["id"], unique=False)
    op.create_index(op.f("ix_generated_reels_slug"), "generated_reels", ["slug"], unique=True)
    op.create_index(op.f("ix_generated_reels_source_url"), "generated_reels", ["source_url"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_generated_reels_source_url"), table_name="generated_reels")
    op.drop_index(op.f("ix_generated_reels_slug"), table_name="generated_reels")
    op.drop_index(op.f("ix_generated_reels_id"), table_name="generated_reels")
    op.drop_table("generated_reels")
