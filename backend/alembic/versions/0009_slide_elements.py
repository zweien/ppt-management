"""slide_elements 表(元素级索引,SE-04)

Revision ID: 0009_slide_elements
Revises: 0008_visibility_folders
Create Date: 2026-07-31

- slide_elements 表:slide 内独立元素(文本框/图片/表格)
- embedding 向量列(pgvector)+ GIN 全文索引 + ivfflat 向量索引
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_slide_elements"
down_revision = "0008_visibility_folders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slide_elements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("element_index", sa.Integer(), nullable=False),
        sa.Column("element_type", sa.String(40), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("image_rId", sa.String(40)),
        sa.Column("image_target", sa.Text()),
        sa.Column("image_position", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("text_search", sa.Text()),  # text 类型(存 jieba 分词文本),GIN 索引用 to_tsvector 转 tsvector
        sa.Column("embedding_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_slide_element_slide", ondelete="CASCADE"),
    )
    op.create_index("ix_slide_elements_slide_id", "slide_elements", ["slide_id"])
    op.create_index("ix_slide_elements_element_type", "slide_elements", ["element_type"])

    # embedding 向量列(pgvector,1024 维 bge-m3;ivfflat 索引需指定维度)
    op.execute("ALTER TABLE slide_elements ADD COLUMN embedding vector(1024);")

    # GIN 全文索引(simple tsvector)
    op.execute(
        "CREATE INDEX ix_slide_elements_text_search ON slide_elements USING gin (to_tsvector('simple', text_search));"
    )

    # ivfflat 向量索引(cosine)
    op.execute(
        "CREATE INDEX ix_slide_elements_embedding ON slide_elements USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_slide_elements_embedding;")
    op.execute("DROP INDEX IF EXISTS ix_slide_elements_text_search;")
    op.drop_index("ix_slide_elements_element_type", table_name="slide_elements")
    op.drop_index("ix_slide_elements_slide_id", table_name="slide_elements")
    op.drop_table("slide_elements")
