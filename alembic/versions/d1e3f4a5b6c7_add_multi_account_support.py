"""add multi-account support

Revision ID: d1e3f4a5b6c7
Revises: c9a8f0f8d2b1
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c9a8f0f8d2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New fb_group_activity table for per-account group tracking
    op.create_table(
        "fb_group_activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("last_liked_date", sa.DateTime(), nullable=True),
        sa.Column("last_marketed_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["fbgroups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "group_id", name="uq_fb_group_activity_account_group"),
    )
    op.create_index(op.f("ix_fb_group_activity_id"), "fb_group_activity", ["id"], unique=False)
    op.create_index(op.f("ix_fb_group_activity_account_id"), "fb_group_activity", ["account_id"], unique=False)
    op.create_index(op.f("ix_fb_group_activity_group_id"), "fb_group_activity", ["group_id"], unique=False)

    # 2. Add account_id to fb_friends, replace unique on profile_url with compound unique
    op.add_column("fb_friends", sa.Column("account_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_fb_friends_account_id"), "fb_friends", ["account_id"], unique=False)
    op.drop_index(op.f("ix_fb_friends_profile_url"), table_name="fb_friends")
    op.create_unique_constraint(
        "uq_fb_friends_account_profile", "fb_friends", ["account_id", "profile_url"]
    )

    # 3. Add account_id to posted_articles, replace unique on url with compound unique
    op.add_column("posted_articles", sa.Column("account_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_posted_articles_account_id"), "posted_articles", ["account_id"], unique=False)
    op.drop_index(op.f("ix_posted_articles_url"), table_name="posted_articles")
    op.create_unique_constraint(
        "uq_posted_articles_account_url", "posted_articles", ["account_id", "url"]
    )


def downgrade() -> None:
    # 3. Revert posted_articles
    op.drop_constraint("uq_posted_articles_account_url", "posted_articles", type_="unique")
    op.drop_index(op.f("ix_posted_articles_account_id"), table_name="posted_articles")
    op.drop_column("posted_articles", "account_id")
    op.create_index(op.f("ix_posted_articles_url"), "posted_articles", ["url"], unique=True)

    # 2. Revert fb_friends
    op.drop_constraint("uq_fb_friends_account_profile", "fb_friends", type_="unique")
    op.drop_index(op.f("ix_fb_friends_account_id"), table_name="fb_friends")
    op.drop_column("fb_friends", "account_id")
    op.create_index(op.f("ix_fb_friends_profile_url"), "fb_friends", ["profile_url"], unique=True)

    # 1. Drop fb_group_activity
    op.drop_index(op.f("ix_fb_group_activity_group_id"), table_name="fb_group_activity")
    op.drop_index(op.f("ix_fb_group_activity_account_id"), table_name="fb_group_activity")
    op.drop_index(op.f("ix_fb_group_activity_id"), table_name="fb_group_activity")
    op.drop_table("fb_group_activity")
