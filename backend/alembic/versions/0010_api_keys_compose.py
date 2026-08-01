"""api_keys + compose_jobs 表(SE-06 AI 拼 PPT 机器认证)

Revision ID: 0010_api_keys_compose
Revises: 0009_slide_elements
Create Date: 2026-08-01

- api_keys:API key(机器认证,只存 sha256 hash)
- compose_jobs:AI 拼 PPT 任务记录(大纲/匹配/产出)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_api_keys_compose"
down_revision = "0009_slide_elements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_apikey_owner"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_hash"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_owner_id", "api_keys", ["owner_id"])

    op.create_table(
        "compose_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("outline", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("matches", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("object_key", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="done"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_compose_owner"),
    )
    op.create_index("ix_compose_jobs_owner_id", "compose_jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_compose_jobs_owner_id", table_name="compose_jobs")
    op.drop_table("compose_jobs")
    op.drop_index("ix_api_keys_owner_id", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
