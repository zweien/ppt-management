"""initial schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions (pgvector + trigram + uuid)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "presentation_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("presentation_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="UPLOADING"),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("original_filename", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_presentation_versions_presentation_id", "presentation_versions", ["presentation_id"])
    op.create_index("ix_presentation_versions_sha256", "presentation_versions", ["sha256"])

    op.create_table(
        "presentations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["current_version_id"], ["presentation_versions.id"], name="fk_pres_current_version", use_alter=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_pres_owner"),
    )

    op.create_table(
        "slides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("native_text", sa.Text()),
        sa.Column("notes_text", sa.Text()),
        sa.Column("mineru_markdown", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("manual_summary", sa.Text()),
        sa.Column("content_json", postgresql.JSONB()),
        sa.Column("preview_object_key", sa.Text()),
        sa.Column("thumbnail_object_key", sa.Text()),
        sa.Column("text_search", sa.Text()),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("visual_phash", sa.String(32)),
        sa.Column("parse_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("user_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["version_id"], ["presentation_versions.id"], name="fk_slides_version"),
        sa.UniqueConstraint("version_id", "page_no", name="uq_slides_version_page"),
    )
    op.create_index("ix_slides_version_id", "slides", ["version_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(60)),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    op.create_table(
        "slide_tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("tag_id", sa.String(36), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Float()),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_st_slide", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_st_tag"),
    )
    op.create_index("ix_slide_tags_slide_id", "slide_tags", ["slide_id"])
    op.create_index("ix_slide_tags_tag_id", "slide_tags", ["tag_id"])

    op.create_table(
        "favorites",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_fav_user"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_fav_slide", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "slide_id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(60)),
        sa.Column("error_message", sa.Text()),
        sa.Column("stage", sa.String(40)),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("log_ref", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_jobs_idempotency"),
    )
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_target_id", "jobs", ["target_id"])

    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(20), nullable=False),
        sa.Column("base_url", sa.Text()),
        sa.Column("api_key_ciphertext", sa.Text()),
        sa.Column("model", sa.String(120)),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("allow_send_raw_image", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_send_raw_text", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "slide_ai_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("model_config_id", sa.String(36), nullable=True),
        sa.Column("prompt_version", sa.String(40)),
        sa.Column("summary", sa.Text()),
        sa.Column("json_result", postgresql.JSONB()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_ai_slide", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], name="fk_ai_model"),
    )
    op.create_index("ix_slide_ai_analyses_slide_id", "slide_ai_analyses", ["slide_id"])

    op.create_table(
        "slide_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("model_config_id", sa.String(36), nullable=True),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_emb_slide", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], name="fk_emb_model"),
    )
    op.create_index("ix_slide_embeddings_slide_id", "slide_embeddings", ["slide_id"])
    # vector column (pgvector) - phase 2 will populate; added now so extension is in use
    op.execute("ALTER TABLE slide_embeddings ADD COLUMN embedding vector;")

    op.create_table(
        "export_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slide_id", sa.String(36), nullable=False),
        sa.Column("object_key", sa.Text()),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], name="fk_export_slide", ondelete="CASCADE"),
    )
    op.create_index("ix_export_files_slide_id", "export_files", ["slide_id"])

    # GIN index on text_search for full-text queries (simple config tsvector)
    op.execute(
        "CREATE INDEX ix_slides_text_search ON slides USING gin (to_tsvector('simple', text_search));"
    )


def downgrade() -> None:
    op.drop_table("export_files")
    op.drop_table("slide_embeddings")
    op.drop_table("slide_ai_analyses")
    op.drop_table("model_configs")
    op.drop_table("jobs")
    op.drop_table("favorites")
    op.drop_table("slide_tags")
    op.drop_table("tags")
    op.drop_table("slides")
    op.drop_table("presentations")
    op.drop_table("presentation_versions")
    op.drop_table("users")
