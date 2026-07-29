"""app_settings table (runtime-configurable settings)

Revision ID: 0005_app_settings
Revises: 0004_version_matches
Create Date: 2026-07-30

业务可调配置 DB 化:上传限制、AI 服务地址、Token 过期、CORS。
DB 无记录时 get_setting 回退 env 默认值,故无需预填种子。
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_app_settings"
down_revision = "0004_version_matches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
