"""add gaokao data tables

Revision ID: 20260411_0004
Revises: 20260411_0003
Create Date: 2026-04-11 01:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0004"
down_revision = "20260411_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gaokao_score_ranks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("track", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "province", "track", "score", name="uq_gaokao_score_rank"),
    )
    op.create_index(op.f("ix_gaokao_score_ranks_year"), "gaokao_score_ranks", ["year"], unique=False)
    op.create_index(op.f("ix_gaokao_score_ranks_province"), "gaokao_score_ranks", ["province"], unique=False)
    op.create_index(op.f("ix_gaokao_score_ranks_track"), "gaokao_score_ranks", ["track"], unique=False)
    op.create_index(op.f("ix_gaokao_score_ranks_score"), "gaokao_score_ranks", ["score"], unique=False)

    op.create_table(
        "gaokao_control_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("track", sa.String(length=32), nullable=False),
        sa.Column("line_type", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "province", "track", "line_type", name="uq_gaokao_control_line"),
    )
    op.create_index(op.f("ix_gaokao_control_lines_year"), "gaokao_control_lines", ["year"], unique=False)
    op.create_index(op.f("ix_gaokao_control_lines_province"), "gaokao_control_lines", ["province"], unique=False)
    op.create_index(op.f("ix_gaokao_control_lines_track"), "gaokao_control_lines", ["track"], unique=False)

    op.create_table(
        "gaokao_admission_baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_year", sa.Integer(), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("track", sa.String(length=32), nullable=False),
        sa.Column("school", sa.String(length=128), nullable=False),
        sa.Column("major", sa.String(length=128), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("school_level", sa.String(length=64), nullable=True),
        sa.Column("batch", sa.String(length=32), nullable=True),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("min_rank", sa.Integer(), nullable=True),
        sa.Column("major_tags", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "data_year",
            "province",
            "track",
            "school",
            "major",
            name="uq_gaokao_admission_baseline",
        ),
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_data_year"),
        "gaokao_admission_baselines",
        ["data_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_province"),
        "gaokao_admission_baselines",
        ["province"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_track"),
        "gaokao_admission_baselines",
        ["track"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_school"),
        "gaokao_admission_baselines",
        ["school"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_min_score"),
        "gaokao_admission_baselines",
        ["min_score"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gaokao_admission_baselines_min_rank"),
        "gaokao_admission_baselines",
        ["min_rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_gaokao_admission_baselines_min_rank"), table_name="gaokao_admission_baselines")
    op.drop_index(op.f("ix_gaokao_admission_baselines_min_score"), table_name="gaokao_admission_baselines")
    op.drop_index(op.f("ix_gaokao_admission_baselines_school"), table_name="gaokao_admission_baselines")
    op.drop_index(op.f("ix_gaokao_admission_baselines_track"), table_name="gaokao_admission_baselines")
    op.drop_index(op.f("ix_gaokao_admission_baselines_province"), table_name="gaokao_admission_baselines")
    op.drop_index(op.f("ix_gaokao_admission_baselines_data_year"), table_name="gaokao_admission_baselines")
    op.drop_table("gaokao_admission_baselines")

    op.drop_index(op.f("ix_gaokao_control_lines_track"), table_name="gaokao_control_lines")
    op.drop_index(op.f("ix_gaokao_control_lines_province"), table_name="gaokao_control_lines")
    op.drop_index(op.f("ix_gaokao_control_lines_year"), table_name="gaokao_control_lines")
    op.drop_table("gaokao_control_lines")

    op.drop_index(op.f("ix_gaokao_score_ranks_score"), table_name="gaokao_score_ranks")
    op.drop_index(op.f("ix_gaokao_score_ranks_track"), table_name="gaokao_score_ranks")
    op.drop_index(op.f("ix_gaokao_score_ranks_province"), table_name="gaokao_score_ranks")
    op.drop_index(op.f("ix_gaokao_score_ranks_year"), table_name="gaokao_score_ranks")
    op.drop_table("gaokao_score_ranks")
