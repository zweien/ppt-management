"""mineru 队列任务:MinerU 增强解析(PRD §9.4, ADR-0006/0007)。

调用宿主机 mineru-api 解析整份 PDF(阶段一已生成 preview.pdf),产出 Markdown,
按页拆分后回填各 slide 的 mineru_markdown。
"""
import logging

from sqlalchemy.orm import Session

from app.core.storage import get_storage, preview_pdf_key
from app.db.session import SessionLocal
from app.models import Job, Presentation, PresentationVersion, Slide
from app.services.jobs import find_or_create_job, mark_failed, mark_running, mark_success
from app.services.mineru_client import parse_pdf_sync

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _split_markdown_by_page(md: str, page_count: int) -> list[str]:
    """MinerU Markdown 常以分页符或空行分页;按 '\f'(form feed)或 '---' 拆分。
    拆不出时回退:整段赋给第一页。"""
    if not md:
        return ["" for _ in range(page_count)]
    # Try form-feed split first (MinerU page delimiter)
    parts = md.split("\f")
    if len(parts) >= page_count:
        return [p.strip() for p in parts[:page_count]]
    # Try splitting on page markers like <!-- page --> or ## 第N页
    import re
    parts = re.split(r"(?:<!--\s*page|##\s*第\s*\d+\s*页|---\s*\n)", md)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= page_count:
        return parts[:page_count]
    # Fallback: cannot reliably split -> whole md to page 1, rest empty
    result = ["" for _ in range(page_count)]
    result[0] = md.strip()
    return result


@celery_app.task(name="app.tasks.mineru.parse_mineru", bind=True, max_retries=1)
def parse_mineru_task(self, version_id: str) -> dict:  # noqa: ANN001
    db: Session = SessionLocal()
    try:
        version = db.get(PresentationVersion, version_id)
        if not version:
            return {"error": "version not found"}
        pres = db.get(Presentation, version.presentation_id)

        job = find_or_create_job(db, "parse_mineru", "version", version_id,
                                 stage="ENRICHING", input_data=version.sha256)
        if job.status == "success":
            return {"skipped": "already enriched"}
        mark_running(db, job)

        storage = get_storage()
        pdf_key = preview_pdf_key(pres.id, version_id)
        if not storage.object_exists(pdf_key):
            mark_failed(db, job, "NO_PDF", "preview.pdf not found; render must complete first")
            return {"error": "no preview.pdf"}

        pdf_bytes = storage.get_object(pdf_key)
        result = parse_pdf_sync(pdf_bytes)
        if not result.success:
            mark_failed(db, job, "MINERU_ERROR", result.error or "unknown")
            return {"error": result.error}

        # Split markdown across slides
        slides = (db.query(Slide).filter(Slide.version_id == version_id)
                  .order_by(Slide.page_no).all())
        page_texts = _split_markdown_by_page(result.markdown, len(slides))
        for slide, text in zip(slides, page_texts):
            slide.mineru_markdown = text or None

        # Promote version status toward READY (enrichment done on mineru side)
        db.commit()
        db.refresh(version)
        if version.status == "BASIC_READY":
            version.status = "ENRICHED"  # mineru done; full READY after ai+embedding
        mark_success(db, job)
        db.commit()
        logger.info("MinerU enriched version %s", version_id)
        return {"version_id": version_id, "md_len": len(result.markdown)}
    except Exception as e:
        logger.exception("parse_mineru failed for %s", version_id)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.job_type == "parse_mineru",
                                       Job.target_id == version_id).first()
            if job:
                mark_failed(db, job, "MINERU_ERROR", str(e)[:500])
        except Exception:
            pass
        raise
    finally:
        db.close()
