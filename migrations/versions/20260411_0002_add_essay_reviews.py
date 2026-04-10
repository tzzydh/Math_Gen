"""add essay reviews

Revision ID: 20260411_0002
Revises: 20260410_0001
Create Date: 2026-04-11 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0002"
down_revision = "20260410_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "essay_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_asset_id", sa.Integer(), nullable=False),
        sa.Column("pdf_asset_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("recognized_title", sa.String(length=255), nullable=True),
        sa.Column("corrected_title", sa.String(length=255), nullable=False),
        sa.Column("recognized_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_max", sa.Integer(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pdf_asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_essay_reviews_user_id"), "essay_reviews", ["user_id"], unique=False)
    op.create_index(op.f("ix_essay_reviews_source_asset_id"), "essay_reviews", ["source_asset_id"], unique=False)
    op.create_index(op.f("ix_essay_reviews_pdf_asset_id"), "essay_reviews", ["pdf_asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_essay_reviews_pdf_asset_id"), table_name="essay_reviews")
    op.drop_index(op.f("ix_essay_reviews_source_asset_id"), table_name="essay_reviews")
    op.drop_index(op.f("ix_essay_reviews_user_id"), table_name="essay_reviews")
    op.drop_table("essay_reviews")
