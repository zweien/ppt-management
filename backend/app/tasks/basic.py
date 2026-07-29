"""basic 队列任务:Open XML 解析、索引构建(PRD §15.1)。

parse_openxml_task:解析源 PPTX → 建 slides → 建全文索引 → 推进状态到 BASIC_READY(文本部分)。
build_search_index:为单 slide 建索引(供查询时按需)。

幂等:用 idempotency_key 防重复创建 slides(§15.3)。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Job, Presentation, PresentationVersion, Slide
from app.services.jobs import find_or_create_job, mark_failed, mark_running, mark_success
from app.services.openxml import normalize_text_for_fingerprint, parse_pptx
from app.services.search import index_slide
from app.services.tokenizer import text_fingerprint_hash

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _fingerprint(native_text: str) -> str:
    norm = normalize_text_for_fingerprint(native_text)
    return text_fingerprint_hash(norm)


def _maybe_match_previous_version(db, version) -> None:
    """若 version 是其 presentation 的非首版本,与其前一个版本做页面匹配(ADR-0008 §2)。"""
    from app.services.versioning import match_versions
    siblings = (
        db.query(PresentationVersion)
        .filter(PresentationVersion.presentation_id == version.presentation_id)
        .order_by(PresentationVersion.version_no)
        .all()
    )
    if len(siblings) < 2:
        return
    # 找到当前版本的前一个
    idx = next((i for i, v in enumerate(siblings) if v.id == version.id), -1)
    if idx <= 0:
        return
    prev = siblings[idx - 1]
    match_versions(db, prev.id, version.id)


@celery_app.task(name="app.tasks.basic.parse_openxml", bind=True, max_retries=2)
def parse_openxml_task(self, version_id: str) -> dict:  # noqa: ANN001
    """Parse a version's source PPTX and create slides."""
    db: Session = SessionLocal()
    try:
        version = db.get(PresentationVersion, version_id)
        if not version:
            return {"error": "version not found"}

        job = find_or_create_job(db, "parse_openxml", "version", version_id,
                                 stage="PARSING", input_data=version.sha256)
        if job.status == "success":
            return {"skipped": "already parsed"}
        mark_running(db, job)

        # Update version status
        version.status = "PARSING"
        db.commit()

        # Fetch source from storage
        from app.core.storage import get_storage
        storage = get_storage()
        content = storage.get_object(version.source_object_key)

        parsed = parse_pptx(content)
        page_count = len(parsed.slides)

        # 取所属 presentation 标题(用于全文索引含文件名,SE-01)
        presentation = db.get(Presentation, version.presentation_id)
        pres_title = presentation.title if presentation else None

        # Idempotent: delete any pre-existing slides for this version (re-parse case)
        db.query(Slide).filter(Slide.version_id == version_id).delete()
        db.commit()

        for ps in parsed.slides:
            fp = _fingerprint(ps.native_text)
            slide = Slide(
                version_id=version_id,
                page_no=ps.page_no,
                title=ps.title,
                native_text=ps.native_text,
                notes_text=ps.notes_text,
                content_json={**ps.content_json, "relationships": ps.relationships},
                fingerprint=fp,
                parse_status="success",
                text_search=None,  # filled by index step below
            )
            db.add(slide)
            db.flush()
            # Build full-text index (app-layer jieba;含标题/正文/备注/表格/文件名 SE-01)
            index_slide(db, slide, pres_title)

        version.page_count = page_count
        # Move to BASIC_READY if render also done, else stay RENDERING-ish; set conservatively
        # (render task will finalize BASIC_READY)
        version.status = "PARSED"
        presentation = db.get(Presentation, version.presentation_id)
        if presentation:
            presentation.page_count = page_count

        mark_success(db, job)
        db.commit()
        logger.info("Parsed version %s: %d slides", version_id, page_count)

        # Trigger render (parallel pipeline)
        from app.tasks.render import render_preview_task
        render_preview_task.delay(version_id)

        # Trigger visual analysis per slide (best-effort; skips if no vision config)
        try:
            from app.tasks.ai import analyze_visual_task
            for s in db.query(Slide).filter(Slide.version_id == version_id).all():
                analyze_visual_task.apply_async(args=[s.id], countdown=20)
        except Exception:
            pass

        # 版本管理:若此版本是某 presentation 的第 2+ 版,与前一个版本做页面匹配(ADR-0008)
        try:
            _maybe_match_previous_version(db, version)
            db.commit()
        except Exception:
            logger.warning("version match skipped for %s", version_id, exc_info=True)

        return {"version_id": version_id, "slides": page_count}
    except Exception as e:
        logger.exception("parse_openxml failed for %s", version_id)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.job_type == "parse_openxml",
                                       Job.target_id == version_id).first()
            v = db.get(PresentationVersion, version_id)
            if v:
                v.status = "PARTIAL_FAILED"
                db.commit()
            if job:
                mark_failed(db, job, "PARSE_ERROR", str(e)[:500])
        except Exception:
            pass
        raise
    finally:
        db.close()
