"""phase2: vector index + mineru markdown already on slides

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-07-29
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADR-0007 §5: fix vector column dimension so ivfflat index can be built.
    # Default dimension 1536 (OpenAI text-embedding-3-small). Switching default
    # embedding config to a different dim requires re-running this alter (part of
    # the ADR-0006 "background recompute" workflow).
    op.execute("ALTER TABLE slide_embeddings ALTER COLUMN embedding TYPE vector(1536);")

    # ivfflat index for vector similarity search (ADR-0003/0007)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_slide_embeddings_embedding "
        "ON slide_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )
    # trigram index on tags name for fuzzy tag matching (SE-02)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tags_name_trgm ON tags USING gin (name gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_slide_embeddings_embedding;")
    op.execute("DROP INDEX IF EXISTS ix_tags_name_trgm;")
    op.execute("ALTER TABLE slide_embeddings ALTER COLUMN embedding TYPE vector;")
