"""add source_format to presentation_versions

Revision ID: 0006_source_format
Revises: 0005_app_settings
Create Date: 2026-07-30

支持 .ppt / .pdf 上传:记录源文件格式(pptx/ppt/pdf)。
存量行回填 'pptx'(此前仅支持 pptx)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_source_format"
down_revision = "0005_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "presentation_versions",
        sa.Column("source_format", sa.String(10), nullable=False, server_default="pptx"),
    )
    # 存量行已是 pptx,server_default 已回填;显式 update 兜底。
    op.execute("UPDATE presentation_versions SET source_format = 'pptx' WHERE source_format IS NULL OR source_format = ''")


def downgrade() -> None:
    op.drop_column("presentation_versions", "source_format")
