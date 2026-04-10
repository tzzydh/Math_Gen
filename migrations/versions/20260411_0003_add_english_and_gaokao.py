"""add english essay subject and gaokao plans

Revision ID: 20260411_0003
Revises: 20260411_0002
Create Date: 2026-04-11 01:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0003"
down_revision = "20260411_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "essay_reviews",
        sa.Column("subject", sa.String(length=32), nullable=False, server_default="chinese"),
    )

    op.create_table(
        "gaokao_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("subject_combination", sa.String(length=128), nullable=False),
        sa.Column("score", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.String(length=32), nullable=True),
        sa.Column("target_json", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gaokao_plans_user_id"), "gaokao_plans", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_gaokao_plans_user_id"), table_name="gaokao_plans")
    op.drop_table("gaokao_plans")
    op.drop_column("essay_reviews", "subject")
