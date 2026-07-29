"""mineru 队列任务:MinerU 增强解析(PRD §9.4, ADR-0006/0007)。

逐页调用宿主机 mineru-api(用阶段一已生成的单页 PNG),保证每页 mineru_markdown 准确归属。
逐页而非整 PDF:MinerU 对整份 PPTX/PDF 返回合并 Markdown,无可靠分页符;
逐页解析自然按页归属,且可并发容错(单页失败不阻断其他页)。
"""
import logging

from sqlalchemy.orm import Session

from app.core.storage import get_storage, slide_preview_key
from app.db.session import SessionLocal
from app.models import Job, Presentation, PresentationVersion, Slide
from app.services.jobs import find_or_create_job, mark_failed, mark_running, mark_success
from app.services.mineru_client import parse_pdf_sync

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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
        slides = (db.query(Slide).filter(Slide.version_id == version_id)
                  .order_by(Slide.page_no).all())
        if not slides:
            mark_failed(db, job, "NO_SLIDES", "no slides to enrich")
            return {"error": "no slides"}

        total = len(slides)
        ok = 0
        for i, slide in enumerate(slides, start=1):
            # 需要 preview PNG(render 产物)
            if not slide.preview_object_key:
                continue
            try:
                png = storage.get_object(slide.preview_object_key)
                res = parse_pdf_sync(png, filename=f"p{slide.page_no}.png")
                if res.success and res.markdown.strip():
                    slide.mineru_markdown = res.markdown.strip()
                    ok += 1
                else:
                    # 单页失败不阻断,保留空 md
                    logger.warning("MinerU page %d failed: %s", slide.page_no, res.error)
            except Exception as e:  # noqa: BLE001
                logger.warning("MinerU page %d exception: %s", slide.page_no, e)
            # 更新进度
            job.progress = int(i / total * 100)
            db.commit()

        db.refresh(version)
        if version.status in ("BASIC_READY", "RENDERING", "PARSED"):
            version.status = "ENRICHED"
        mark_success(db, job)
        db.commit()
        logger.info("MinerU enriched version %s: %d/%d pages", version_id, ok, total)
        return {"version_id": version_id, "pages": ok, "total": total}
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
