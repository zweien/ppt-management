"""phase3: version_slide_matches table

Revision ID: 0004_version_matches
Revises: 0003_emb_dim_1024
Create Date: 2026-07-29

ADR-0008 §2:版本间页面变化匹配结果表。
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_version_matches"
down_revision = "0003_emb_dim_1024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "version_slide_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_slide_id", sa.String(36), nullable=False),
        sa.Column("to_slide_id", sa.String(36), nullable=False),
        # from_version_id / to_version_id 冗余便于查询
        sa.Column("from_version_id", sa.String(36), nullable=False),
        sa.Column("to_version_id", sa.String(36), nullable=False),
        # match_type: unchanged / modified / added / deleted / rearranged
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["from_slide_id"], ["slides.id"], name="fk_vsm_from", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_slide_id"], ["slides.id"], name="fk_vsm_to", ondelete="CASCADE"),
    )
    op.create_index("ix_vsm_from_version", "version_slide_matches", ["from_version_id"])
    op.create_index("ix_vsm_to_version", "version_slide_matches", ["to_version_id"])


def downgrade() -> None:
    op.drop_index("ix_vsm_to_version", table_name="version_slide_matches")
    op.drop_index("ix_vsm_from_version", table_name="version_slide_matches")
    op.drop_table("version_slide_matches")
