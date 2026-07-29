"""embedding 维度改为 1024(bge-m3)

Revision ID: 0003_emb_dim_1024
Revises: 0002_phase2
Create Date: 2026-07-29

ADR-0007 §5 / ADR-0008:default embedding 配置切换为 bge-m3(1024 维),需把
slide_embeddings.embedding 列从 0002 的 vector(1536) 改为 vector(1024),并重建
ivfflat 索引。迁移时该表为空(0 行),ALTER 维度安全;后续换模型若维度不同需按
ADR-0006「后台重算」工作流重建该列。
"""
from alembic import op

revision = "0003_emb_dim_1024"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 重建前先删旧维度索引(ALTER TYPE 前索引必须不存在)
    op.execute("DROP INDEX IF EXISTS ix_slide_embeddings_embedding;")
    # 维度 1536(OpenAI) -> 1024(bge-m3)
    op.execute("ALTER TABLE slide_embeddings ALTER COLUMN embedding TYPE vector(1024);")
    # 重建 ivfflat 余弦索引(与 0002 一致:vector_cosine_ops, lists=100)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_slide_embeddings_embedding "
        "ON slide_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_slide_embeddings_embedding;")
    op.execute("ALTER TABLE slide_embeddings ALTER COLUMN embedding TYPE vector(1536);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_slide_embeddings_embedding "
        "ON slide_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )
