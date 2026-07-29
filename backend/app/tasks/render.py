"""render 队列任务:LibreOffice 转 PDF + 生成页面 PNG/缩略图(PRD §9.3, ADR-0005)。

并发模型:每个 worker-render 容器单 profile 单并发(celery 配置 prefetch=1 + --concurrency=1)。
常驻 soffice 复用由 LibreOffice 自身进程管理;容器 restart=unless-stopped 自愈。
"""
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.storage import get_storage, preview_pdf_key, slide_preview_key, slide_thumb_key
from app.db.session import SessionLocal
from app.models import Job, Presentation, PresentationVersion, Slide
from app.services.jobs import find_or_create_job, mark_failed, mark_running, mark_success

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Persistent LO profile per container (ADR-0005). Single concurrency per container
# (celery prefetch=1, concurrency=1) ensures no two soffice instances share this profile.
LO_PROFILE = "/tmp/lo-profile-render"
os.makedirs(LO_PROFILE, exist_ok=True)

RENDER_TIMEOUT = 60  # seconds per page (PRD §19.2)


def _cleanup_lo_locks() -> None:
    """Remove stale LO lock files (ADR-0005: container restart also cleans these)."""
    import glob
    for lock in glob.glob(f"{LO_PROFILE}/**/.lock", recursive=True):
        try:
            os.remove(lock)
        except OSError:
            pass


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _libreoffice_to_pdf(pptx_path: str, out_dir: str) -> str:
    """Convert PPTX -> PDF using a persistent profile (single concurrency per container).

    The output filename is <pptx-basename>.pdf, NOT 'preview.pdf'.
    """
    _cleanup_lo_locks()
    # Kill any lingering soffice instance first (defensive; single-concurrency)
    _run(["pkill", "-f", "soffice"], timeout=10)
    time.sleep(0.5)

    cmd = [
        "soffice", "--headless",
        f"-env:UserInstallation=file://{LO_PROFILE}",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        pptx_path,
    ]
    rc, out, err = _run(cmd, timeout=300)
    # LO writes <basename>.pdf
    base = os.path.splitext(os.path.basename(pptx_path))[0]
    pdf_path = os.path.join(out_dir, f"{base}.pdf")
    # javaldx warning is harmless noise on stderr; the real signal is the PDF existing
    if not os.path.exists(pdf_path):
        raise RuntimeError(
            f"LibreOffice convert produced no PDF (rc={rc}): {err.strip()[:300]}"
        )
    return pdf_path


def _pdf_to_images(pdf_path: str, out_dir: str, page_count: int) -> list[tuple[str, str]]:
    """Render each PDF page to PNG (1920 wide) + WebP thumb (480 wide)."""
    # Use pdftoppm (poppler-utils)
    prefix = os.path.join(out_dir, "slide")
    cmd = ["pdftoppm", "-png", "-r", "150", pdf_path, prefix]
    rc, out, err = _run(cmd, timeout=300)
    if rc != 0:
        raise RuntimeError(f"pdftoppm failed: {err.strip()[:300]}")
    pairs = []
    png_files = sorted(Path(out_dir).glob("slide-*.png"))
    for i, png in enumerate(png_files, start=1):
        # Downscale high-res PNG to ~1920 wide using ImageMagick if available, else keep
        hi = png
        # Thumbnail via pdftoppm second pass at lower res OR imagemagick
        thumb = png.with_name(f"thumb-{i:04d}.png")
        magick_rc, _, _ = _run(["convert", str(png), "-resize", "480x>",
                                str(thumb)], timeout=60)
        pairs.append((str(hi), str(thumb)))
    return pairs


@celery_app.task(name="app.tasks.render.render_preview", bind=True, max_retries=1)
def render_preview_task(self, version_id: str) -> dict:  # noqa: ANN001
    db: Session = SessionLocal()
    try:
        version = db.get(PresentationVersion, version_id)
        if not version:
            return {"error": "version not found"}

        job = find_or_create_job(db, "render_preview", "version", version_id,
                                 stage="RENDERING", input_data=version.sha256)
        if job.status == "success":
            return {"skipped": "already rendered"}
        mark_running(db, job)

        version.status = "RENDERING"
        db.commit()

        pres = db.get(Presentation, version.presentation_id)
        pres_id = pres.id if pres else "unknown"

        storage = get_storage()
        content = storage.get_object(version.source_object_key)

        workdir = tempfile.mkdtemp(prefix="render_")
        try:
            pptx_path = os.path.join(workdir, "source.pptx")
            with open(pptx_path, "wb") as f:
                f.write(content)

            pdf_path = _libreoffice_to_pdf(pptx_path, workdir)
            # Store PDF
            with open(pdf_path, "rb") as f:
                storage.put_object(preview_pdf_key(pres_id, version_id), f.read(),
                                   content_type="application/pdf")

            image_pairs = _pdf_to_images(pdf_path, workdir, version.page_count)

            # Attach to slides
            slides = (db.query(Slide).filter(Slide.version_id == version_id)
                      .order_by(Slide.page_no).all())
            slide_by_page = {s.page_no: s for s in slides}

            for i, (hi, thumb) in enumerate(image_pairs, start=1):
                slide = slide_by_page.get(i)
                if not slide:
                    continue
                # High-res PNG
                with open(hi, "rb") as f:
                    png_bytes = f.read()
                png_key = slide_preview_key(pres_id, version_id, i)
                storage.put_object(png_key, png_bytes, content_type="image/png")
                # Thumbnail (convert to webp via imagemagick if available)
                webp_key = slide_thumb_key(pres_id, version_id, i)
                webp_tmp = os.path.join(workdir, f"thumb-{i:04d}.webp")
                rc, _, _ = _run(["convert", thumb, "-quality", "80", webp_tmp], timeout=60)
                if rc == 0 and os.path.exists(webp_tmp):
                    with open(webp_tmp, "rb") as f:
                        storage.put_object(webp_key, f.read(), content_type="image/webp")
                    slide.thumbnail_object_key = webp_key
                else:
                    with open(thumb, "rb") as f:
                        storage.put_object(webp_key, f.read(), content_type="image/png")
                    slide.thumbnail_object_key = webp_key
                slide.preview_object_key = png_key

            # If parse already done (PARSED), promote to BASIC_READY
            db.commit()
            db.refresh(version)
            if version.status in ("RENDERING", "PARSED"):
                version.status = "BASIC_READY"
            mark_success(db, job)
            db.commit()
            logger.info("Rendered version %s: %d pages", version_id, len(image_pairs))
            return {"version_id": version_id, "pages": len(image_pairs)}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    except Exception as e:
        logger.exception("render_preview failed for %s", version_id)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.job_type == "render_preview",
                                       Job.target_id == version_id).first()
            v = db.get(PresentationVersion, version_id)
            if v and v.status != "BASIC_READY":
                v.status = "PARTIAL_FAILED"
                db.commit()
            if job:
                mark_failed(db, job, "RENDER_ERROR", str(e)[:500])
        except Exception:
            pass
        raise
    finally:
        db.close()
