"""SQLAlchemy ORM models — core entities (PRD §12.1).

术语遵守 CONTEXT.md glossary:Presentation / Version / Slide / 原生文字 / 人工标签 等。
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.session import Base


# pgvector; imported lazily-safe (extension created by migration)
try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - only at import time without extension
    Vector = None  # type: ignore[assignment]


class TSVector(TypeDecorator):
    """Stores the application-segmented tsvector (ADR-0004)."""
    impl = Text
    cache_ok = True


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------- Timestamps mixin ----------

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------- User ----------

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------- Presentation ----------

class Presentation(Base, TimestampMixin):
    __tablename__ = "presentations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("presentation_versions.id", use_alter=True), nullable=True
    )
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # denormalized page count of current version
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    versions: Mapped[list["PresentationVersion"]] = relationship(
        back_populates="presentation", foreign_keys="PresentationVersion.presentation_id"
    )


# ---------- Version (immutable) ----------

class PresentationVersion(Base, TimestampMixin):
    __tablename__ = "presentation_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    presentation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("presentations.id"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # status: UPLOADING/VALIDATING/PARSING/RENDERING/BASIC_READY/ENRICHING/READY/PARTIAL_FAILED
    status: Mapped[str] = mapped_column(String(40), default="UPLOADING", nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False, default="")

    presentation: Mapped[Presentation] = relationship(
        back_populates="versions", foreign_keys=[presentation_id]
    )
    slides: Mapped[list["Slide"]] = relationship(back_populates="version")


# ---------- Slide (core asset entity) ----------

class Slide(Base, TimestampMixin):
    __tablename__ = "slides"
    __table_args__ = (UniqueConstraint("version_id", "page_no", name="uq_slides_version_page"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("presentation_versions.id"), nullable=False, index=True
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    native_text: Mapped[str | None] = mapped_column(Text)
    notes_text: Mapped[str | None] = mapped_column(Text)
    mineru_markdown: Mapped[str | None] = mapped_column(Text)  # phase 2
    ai_summary: Mapped[str | None] = mapped_column(Text)  # phase 2
    manual_summary: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preview_object_key: Mapped[str | None] = mapped_column(Text)
    thumbnail_object_key: Mapped[str | None] = mapped_column(Text)
    # tsvector stored as text; segmented by app-layer jieba (ADR-0004)
    text_search: Mapped[str | None] = mapped_column(TSVector)
    fingerprint: Mapped[str | None] = mapped_column(String(64))  # native text normalized hash
    visual_phash: Mapped[str | None] = mapped_column(String(32))  # phase 3
    parse_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    ai_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    user_note: Mapped[str | None] = mapped_column(Text)  # user note (SL-02)

    version: Mapped[PresentationVersion] = relationship(back_populates="slides")


# ---------- AI analyses / embeddings (phase 2, schema ready) ----------

class SlideAIAnalysis(Base, TimestampMixin):
    __tablename__ = "slide_ai_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slide_id: Mapped[str] = mapped_column(String(36), ForeignKey("slides.id"), nullable=False, index=True)
    model_config_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_configs.id"), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[str | None] = mapped_column(Text)
    json_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)


class SlideEmbedding(Base, TimestampMixin):
    __tablename__ = "slide_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slide_id: Mapped[str] = mapped_column(String(36), ForeignKey("slides.id"), nullable=False, index=True)
    model_config_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_configs.id"), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # vector column added by migration (pgvector), optional in phase 1


# ---------- Tags ----------

class Tag(Base, TimestampMixin):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(60))  # 主题/用途/形态/风格/场景/项目/自定义
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # system/ai/manual
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class SlideTag(Base, TimestampMixin):
    __tablename__ = "slide_tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slide_id: Mapped[str] = mapped_column(String(36), ForeignKey("slides.id"), nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id"), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual/ai
    confidence: Mapped[float | None] = mapped_column(Float)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------- Favorites ----------

class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    slide_id: Mapped[str] = mapped_column(String(36), ForeignKey("slides.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------- Jobs ----------

class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # validate/parse_openxml/render_preview/...
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)  # version/presentation/slide
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/running/success/failed
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    log_ref: Mapped[str | None] = mapped_column(Text)


# ---------- Model configs (phase 2, schema ready) ----------

class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(20), nullable=False)  # text/vision/embedding
    base_url: Mapped[str | None] = mapped_column(Text)
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    allow_send_raw_image: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_send_raw_text: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ---------- Export files (phase 3, schema ready) ----------

class ExportFile(Base, TimestampMixin):
    __tablename__ = "export_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slide_id: Mapped[str] = mapped_column(String(36), ForeignKey("slides.id"), nullable=False, index=True)
    object_key: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
