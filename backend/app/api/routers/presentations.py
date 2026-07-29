"""Presentations / versions / slides 路由(§14.1)。"""
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.storage import get_storage
from app.db.session import get_db
from app.models import Presentation, PresentationVersion, Slide, User
from app.schemas.presentation import (
    PresentationOut,
    SlideDetail,
    SlideOut,
    VersionOut,
)
from app.services.jobs import find_or_create_job

router = APIRouter(prefix="/api", tags=["presentations"])


def _presentation_to_out(db: Session, pres: Presentation) -> PresentationOut:
    versions = (
        db.query(PresentationVersion)
        .filter(PresentationVersion.presentation_id == pres.id)
        .order_by(PresentationVersion.version_no)
        .all()
    )
    cur_status = None
    if pres.current_version_id:
        cv = db.get(PresentationVersion, pres.current_version_id)
        if cv:
            cur_status = cv.status
    return PresentationOut(
        id=pres.id,
        title=pres.title,
        page_count=pres.page_count,
        current_version_id=pres.current_version_id,
        deleted_at=pres.deleted_at,
        created_at=pres.created_at,
        versions=[VersionOut(
            id=v.id, presentation_id=v.presentation_id, version_no=v.version_no,
            sha256=v.sha256, page_count=v.page_count, status=v.status,
            file_size=v.file_size, original_filename=v.original_filename, created_at=v.created_at,
        ) for v in versions],
        current_status=cur_status,
    )


@router.get("/presentations", response_model=list[PresentationOut])
def list_presentations(
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PresentationOut]:
    q = db.query(Presentation)
    if not include_deleted:
        q = q.filter(Presentation.deleted_at.is_(None))
    items = q.order_by(Presentation.created_at.desc()).all()
    return [_presentation_to_out(db, p) for p in items]


@router.get("/presentations/{pres_id}", response_model=PresentationOut)
def get_presentation(pres_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> PresentationOut:
    pres = db.get(Presentation, pres_id)
    if not pres or (pres.deleted_at is not None):
        raise HTTPException(status_code=404, detail="文件不存在")
    return _presentation_to_out(db, pres)


@router.delete("/presentations/{pres_id}")
def delete_presentation(pres_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    from datetime import datetime, timezone
    pres.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "已移入回收站"}


@router.post("/presentations/{pres_id}/restore")
def restore_presentation(pres_id: str, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> dict:
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    pres.deleted_at = None
    db.commit()
    return {"detail": "已恢复"}


@router.post("/presentations/{pres_id}/reparse")
def reparse_presentation(pres_id: str, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> dict:
    """对已上传文件重新触发增强解析流水线(MinerU + 视觉 + embedding)。

    要求源文件已完成基础解析与渲染(状态 BASIC_READY 以上,有 preview.pdf)。
    """
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    version = db.get(PresentationVersion, pres.current_version_id) if pres.current_version_id else None
    if not version:
        raise HTTPException(status_code=400, detail="当前版本不存在")
    if version.status not in ("BASIC_READY", "ENRICHED", "READY", "PARSED", "RENDERING", "PARTIAL_FAILED"):
        raise HTTPException(status_code=400, detail=f"文件尚未完成基础解析(当前 {version.status})")

    # 重置该版本上失败/成功的增强任务,使其可重跑(幂等键复用)
    from app.models import Job
    from app.services.jobs import find_or_create_job
    db.query(Job).filter(
        Job.target_id == version.id, Job.job_type.in_(["parse_mineru"])
    ).update({Job.status: "pending", Job.error_code: None, Job.error_message: None,
              Job.started_at: None, Job.finished_at: None, Job.progress: 0}, synchronize_session=False)
    db.commit()

    # 触发 MinerU(视觉/embedding 由配置驱动,在 mineru 之外独立触发)
    try:
        from app.tasks.mineru import parse_mineru_task
        parse_mineru_task.delay(version.id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"无法投递 MinerU 任务:{e}")

    # 若配置了 default vision,顺带重跑视觉分析
    try:
        from app.models import ModelConfig
        has_vision = db.query(ModelConfig).filter(
            ModelConfig.capability == "vision", ModelConfig.is_default.is_(True), ModelConfig.is_enabled.is_(True)
        ).first()
        if has_vision:
            from app.tasks.ai import analyze_visual_task
            from app.models import Slide
            for s in db.query(Slide).filter(Slide.version_id == version.id).all():
                db.query(Job).filter(Job.target_id == s.id, Job.job_type == "analyze_visual").update(
                    {Job.status: "pending", Job.error_code: None, Job.error_message: None}, synchronize_session=False)
                analyze_visual_task.delay(s.id)
            db.commit()
    except Exception:
        pass

    return {"detail": "已重新触发增强解析,可在任务中心查看进度"}


@router.get("/pages", response_model=list[SlideOut])
def browse_pages(
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlideOut]:
    """全库页面瀑布流(当前版本,未删除)。"""
    storage = get_storage()
    rows = (
        db.query(Slide, Presentation.title.label("pres_title"))
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(Presentation.current_version_id == PresentationVersion.id)
        .order_by(Presentation.created_at.desc(), Slide.page_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = []
    for s, pres_title in rows:
        prev = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append(SlideOut.from_model(s, preview_url=prev, thumbnail_url=thumb, presentation_title=pres_title))
    return out


@router.get("/presentations/{pres_id}/slides", response_model=list[SlideOut])
def list_slides(
    pres_id: str,
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlideOut]:
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    vid = version_id or pres.current_version_id
    if not vid:
        return []
    storage = get_storage()
    slides = (
        db.query(Slide)
        .filter(Slide.version_id == vid)
        .order_by(Slide.page_no)
        .all()
    )
    out = []
    for s in slides:
        prev_url = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb_url = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append(SlideOut.from_model(s, preview_url=prev_url, thumbnail_url=thumb_url, presentation_title=pres.title))
    return out


@router.get("/slides/{slide_id}", response_model=SlideDetail)
def get_slide(slide_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> SlideDetail:
    s = db.get(Slide, slide_id)
    if not s:
        raise HTTPException(status_code=404, detail="页面不存在")
    storage = get_storage()
    prev_url = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
    thumb_url = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
    version = db.get(PresentationVersion, s.version_id)
    pres = db.get(Presentation, version.presentation_id) if version else None
    return SlideDetail(
        id=s.id, version_id=s.version_id, page_no=s.page_no, title=s.title,
        native_text=s.native_text, notes_text=s.notes_text, manual_summary=s.manual_summary,
        ai_summary=s.ai_summary, preview_object_key=s.preview_object_key,
        thumbnail_object_key=s.thumbnail_object_key, parse_status=s.parse_status,
        user_note=s.user_note, fingerprint=s.fingerprint,
        preview_url=prev_url, thumbnail_url=thumb_url,
        content_json=s.content_json, presentation_title=pres.title if pres else None,
        mineru_markdown=s.mineru_markdown,
    )


@router.patch("/slides/{slide_id}", response_model=SlideOut)
def patch_slide(slide_id: str, body: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> SlideOut:
    s = db.get(Slide, slide_id)
    if not s:
        raise HTTPException(status_code=404, detail="页面不存在")
    allowed = {"title", "manual_summary", "user_note"}
    for k, v in body.items():
        if k in allowed:
            setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return SlideOut.from_model(s)


@router.get("/presentations/{pres_id}/download-source")
def download_source(pres_id: str, version_id: str | None = Query(None),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    vid = version_id or pres.current_version_id
    version = db.get(PresentationVersion, vid)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    storage = get_storage()
    data = storage.get_object(version.source_object_key)
    fname = version.original_filename or "source.pptx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
