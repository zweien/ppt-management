"""ai 队列任务(ADR-0007):视觉结构化分析 + Embedding 生成。

依赖模型配置中心的 default 配置(ADR-0006 配置驱动)。无 default 配置时跳过并标记。
"""
import hashlib
import logging

from sqlalchemy import func, text as _sa_text
from sqlalchemy.orm import Session

from app.core.storage import get_storage
from app.db.session import SessionLocal
from app.models import (
    Job, ModelConfig, PresentationVersion, Slide, SlideAIAnalysis, SlideEmbedding, SlideTag, Tag,
)
from app.services.jobs import find_or_create_job, mark_failed, mark_running, mark_success
from app.services.model_provider import ModelProvider
from app.services.search import build_text_search
from app.services.vision_analyzer import analyze_slide_image

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_default_config(db: Session, capability: str) -> ModelConfig | None:
    return (
        db.query(ModelConfig)
        .filter(ModelConfig.capability == capability, ModelConfig.is_default.is_(True), ModelConfig.is_enabled.is_(True))
        .first()
    )


# ============ 视觉分析 ============

@celery_app.task(name="app.tasks.ai.analyze_visual", bind=True, max_retries=1)
def analyze_visual_task(self, slide_id: str) -> dict:  # noqa: ANN001
    """对单页做视觉分析,产出 AI 摘要 + AI 标签。"""
    db: Session = SessionLocal()
    try:
        slide = db.get(Slide, slide_id)
        if not slide:
            return {"error": "slide not found"}
        config = _get_default_config(db, "vision")
        if not config:
            slide.ai_status = "skipped"
            db.commit()
            return {"skipped": "no default vision config"}

        job = find_or_create_job(db, "analyze_visual", "slide", slide_id, stage="ENRICHING")
        if job.status == "success":
            return {"skipped": "already analyzed"}
        mark_running(db, job)

        if not slide.preview_object_key:
            mark_failed(db, job, "NO_PREVIEW", "preview image not found")
            return {"error": "no preview"}

        storage = get_storage()
        img_bytes = storage.get_object(slide.preview_object_key)
        result = analyze_slide_image(config, img_bytes)
        if not result.success:
            slide.ai_status = "failed"
            mark_failed(db, job, "VISION_ERROR", result.error or "unknown")
            db.commit()
            return {"error": result.error}

        analysis = result.analysis
        ai = SlideAIAnalysis(
            slide_id=slide_id, model_config_id=config.id,
            prompt_version="v1", summary=analysis.get("summary"),
            json_result=analysis, status="success",
        )
        db.add(ai)
        db.flush()
        slide.ai_summary = analysis.get("summary")
        slide.ai_status = "success"

        # AI tags: clear prior unconfirmed AI tags, then create fresh (CONTEXT.md 数据优先级)
        db.query(SlideTag).filter(
            SlideTag.slide_id == slide_id, SlideTag.origin == "ai", SlideTag.is_confirmed.is_(False)
        ).delete()
        for category, values in [
            ("主题", analysis.get("topics")),
            ("页面用途", analysis.get("page_purpose")),
            ("内容形态", analysis.get("content_types")),
            ("视觉风格", analysis.get("visual_styles")),
            ("适用场景", analysis.get("use_cases")),
        ]:
            for v in (values or []):
                if not v:
                    continue
                tag = db.query(Tag).filter(Tag.name == v).first()
                if not tag:
                    tag = Tag(name=v, category=category, source="ai", status="active")
                    db.add(tag)
                    db.flush()
                exists = db.query(SlideTag).filter(
                    SlideTag.slide_id == slide_id, SlideTag.tag_id == tag.id
                ).first()
                if not exists:
                    db.add(SlideTag(slide_id=slide_id, tag_id=tag.id, origin="ai",
                                    confidence=analysis.get("confidence"), is_confirmed=False))

        mark_success(db, job)
        db.commit()
        logger.info("Visual analysis done for slide %s", slide_id)
        build_embedding_task.delay(slide_id)
        return {"slide_id": slide_id, "topics": analysis.get("topics")}
    except Exception as e:
        logger.exception("analyze_visual failed for %s", slide_id)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.job_type == "analyze_visual",
                                       Job.target_id == slide_id).first()
            if job:
                mark_failed(db, job, "VISION_ERROR", str(e)[:500])
        except Exception:
            pass
        raise
    finally:
        db.close()


# ============ Embedding ============

@celery_app.task(name="app.tasks.ai.build_embedding", bind=True, max_retries=1)
def build_embedding_task(self, slide_id: str) -> dict:  # noqa: ANN001
    """为单页生成 embedding(配置驱动 default,ADR-0006)。"""
    db: Session = SessionLocal()
    try:
        slide = db.get(Slide, slide_id)
        if not slide:
            return {"error": "slide not found"}
        config = _get_default_config(db, "embedding")
        if not config:
            return {"skipped": "no default embedding config"}

        job = find_or_create_job(db, "build_embedding", "slide", slide_id, stage="ENRICHING")
        if job.status == "success":
            return {"skipped": "already embedded"}
        mark_running(db, job)

        text = build_text_search(slide)
        if not text.strip():
            mark_failed(db, job, "EMPTY_TEXT", "no text to embed")
            return {"error": "empty text"}

        source_hash = hashlib.sha256(text.encode()).hexdigest()
        existing = db.query(SlideEmbedding).filter(
            SlideEmbedding.slide_id == slide_id,
            SlideEmbedding.model_config_id == config.id,
            SlideEmbedding.source_hash == source_hash,
            SlideEmbedding.status == "success",
        ).first()
        if existing:
            mark_success(db, job)
            return {"skipped": "same source already embedded"}

        provider = ModelProvider(config, timeout=60.0)
        r = provider.embed(text)
        if not r.success or not r.embedding:
            mark_failed(db, job, "EMBED_ERROR", r.error or "no embedding returned")
            return {"error": r.error}

        vec = r.embedding
        db.query(SlideEmbedding).filter(
            SlideEmbedding.slide_id == slide_id, SlideEmbedding.model_config_id == config.id
        ).delete()
        emb = SlideEmbedding(slide_id=slide_id, model_config_id=config.id,
                             source_hash=source_hash, status="success")
        db.add(emb)
        db.flush()
        vec_literal = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
        db.execute(_sa_text("UPDATE slide_embeddings SET embedding = CAST(:vec AS vector) WHERE id = :eid"),
                   {"eid": emb.id, "vec": vec_literal})

        version = db.get(PresentationVersion, slide.version_id)
        if version:
            _maybe_promote_ready(db, version)

        mark_success(db, job)
        db.commit()
        logger.info("Embedding built for slide %s (dim=%d)", slide_id, len(vec))
        return {"slide_id": slide_id, "dim": len(vec)}
    except Exception as e:
        logger.exception("build_embedding failed for %s", slide_id)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.job_type == "build_embedding",
                                       Job.target_id == slide_id).first()
            if job:
                mark_failed(db, job, "EMBED_ERROR", str(e)[:500])
        except Exception:
            pass
        raise
    finally:
        db.close()


def _maybe_promote_ready(db: Session, version: PresentationVersion) -> None:
    """若该版本所有 slide 都有成功 embedding 与视觉分析,推进到 READY。"""
    total = db.query(func.count(Slide.id)).filter(Slide.version_id == version.id).scalar()
    if not total:
        return
    with_emb = (
        db.query(func.count(SlideEmbedding.id))
        .join(Slide, SlideEmbedding.slide_id == Slide.id)
        .filter(Slide.version_id == version.id, SlideEmbedding.status == "success")
        .scalar()
    )
    with_ai = (
        db.query(func.count(SlideAIAnalysis.id))
        .join(Slide, SlideAIAnalysis.slide_id == Slide.id)
        .filter(Slide.version_id == version.id, SlideAIAnalysis.status == "success")
        .scalar()
    )
    if with_emb >= total and with_ai >= total:
        version.status = "READY"
