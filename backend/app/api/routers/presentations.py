"""Presentations / versions / slides 路由(§14.1)。"""
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import can_access, can_modify, get_current_user
from app.core.storage import get_storage
from app.db.session import get_db
from app.models import (
    Favorite,
    Job,
    Presentation,
    PresentationVersion,
    Slide,
    SlideTag,
    User,
    VersionSlideMatch,
)
from app.schemas.presentation import (
    PresentationOut,
    SlideDetail,
    SlideOut,
    VersionOut,
)
from app.services.favorites import favorite_slide_ids, is_favorite
from app.services.jobs import find_or_create_job

router = APIRouter(prefix="/api", tags=["presentations"])

# Statuses considered "in progress" — for these we surface the latest Job's
# progress/stage so the file list can show a parse progress bar.
PROCESSING_STATUSES = {
    "UPLOADING", "VALIDATING", "PARSING", "RENDERING", "ENRICHING", "BASIC_READY",
}


def _latest_jobs_for_versions(db: Session, version_ids: list[str]) -> dict[str, Job]:
    """Batch-fetch the most recent Job per version id (target_id == version_id).
    Returns a dict {version_id: Job}. One query, N+1-safe."""
    if not version_ids:
        return {}
    rows = (
        db.query(Job)
        .filter(Job.target_id.in_(version_ids))
        .order_by(Job.target_id, Job.created_at.desc())
        .all()
    )
    latest: dict[str, Job] = {}
    for r in rows:
        # rows are ordered so the first seen per target_id is the newest
        if r.target_id not in latest:
            latest[r.target_id] = r
    return latest


def _presentation_to_out(
    db: Session,
    pres: Presentation,
    progress_map: dict[str, Job] | None = None,
    owner_map: dict[str, str] | None = None,
) -> PresentationOut:
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
    # Resolve parse progress for in-progress files.
    parse_progress: int | None = None
    parse_stage: str | None = None
    if pres.current_version_id and cur_status in PROCESSING_STATUSES and progress_map is not None:
        job = progress_map.get(pres.current_version_id)
        if job is not None:
            parse_progress = job.progress
            parse_stage = job.stage
    return PresentationOut(
        id=pres.id,
        title=pres.title,
        page_count=pres.page_count,
        current_version_id=pres.current_version_id,
        deleted_at=pres.deleted_at,
        created_at=pres.created_at,
        visibility=getattr(pres, "visibility", "team") or "team",
        folder_id=getattr(pres, "folder_id", None),
        owner_id=pres.owner_id,
        owner_name=(owner_map or {}).get(pres.owner_id) if owner_map else None,
        versions=[VersionOut(
            id=v.id, presentation_id=v.presentation_id, version_no=v.version_no,
            sha256=v.sha256, page_count=v.page_count, status=v.status,
            file_size=v.file_size, original_filename=v.original_filename, created_at=v.created_at,
            source_format=getattr(v, "source_format", "pptx") or "pptx",
        ) for v in versions],
        current_status=cur_status,
        parse_progress=parse_progress,
        parse_stage=parse_stage,
    )


def _visibility_filter(q, user: User):
    """列表查询加可见性过滤:超管无过滤;普通用户 = team 共享 + 自己的 private。"""
    if user.is_superuser:
        return q
    return q.filter(or_(
        Presentation.visibility == "team",
        Presentation.owner_id == user.id,
    ))


@router.get("/presentations", response_model=list[PresentationOut])
def list_presentations(
    include_deleted: bool = Query(False),
    status_filter: str | None = Query(None, alias="status"),
    folder_id: str | None = Query(None),
    q: str | None = Query(None),
    sort: str = Query("created", pattern="^(created|page_count|title)$"),
    visibility: str | None = Query(None, pattern="^(team|private)$"),
    mine: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PresentationOut]:
    query = db.query(Presentation)
    if not include_deleted:
        query = query.filter(Presentation.deleted_at.is_(None))
    # 可见性过滤(团队私有素材)
    query = _visibility_filter(query, user)
    if visibility:
        query = query.filter(Presentation.visibility == visibility)
    if folder_id:
        query = query.filter(Presentation.folder_id == folder_id)
    if mine:
        query = query.filter(Presentation.owner_id == user.id)
    if q:
        query = query.filter(Presentation.title.ilike(f"%{q}%"))
    # 排序
    sort_col = {
        "created": Presentation.created_at.desc(),
        "page_count": Presentation.page_count.desc(),
        "title": Presentation.title.asc(),
    }[sort]
    items = query.order_by(sort_col).all()
    # 可选:按状态过滤(需 join version status)
    if status_filter:
        items = [p for p in items if _current_status_of(db, p) == status_filter]
    # Batch-fetch current-version statuses to decide which need progress.
    cv_ids = [p.current_version_id for p in items if p.current_version_id]
    cv_status: dict[str, str] = {}
    if cv_ids:
        for v in db.query(PresentationVersion).filter(PresentationVersion.id.in_(cv_ids)).all():
            cv_status[v.id] = v.status
    in_progress_cvs = [vid for vid in cv_ids if cv_status.get(vid) in PROCESSING_STATUSES]
    progress_map = _latest_jobs_for_versions(db, in_progress_cvs)
    # Batch-fetch owner names(上传者显示)
    owner_ids = list({p.owner_id for p in items if p.owner_id})
    owner_map: dict[str, str] = {}
    if owner_ids:
        from app.models import User as UserModel
        for u in db.query(UserModel).filter(UserModel.id.in_(owner_ids)).all():
            owner_map[u.id] = u.display_name or u.username
    return [_presentation_to_out(db, p, progress_map, owner_map) for p in items]


def _current_status_of(db: Session, pres: Presentation) -> str | None:
    if not pres.current_version_id:
        return None
    cv = db.get(PresentationVersion, pres.current_version_id)
    return cv.status if cv else None


@router.get("/presentations/{pres_id}", response_model=PresentationOut)
def get_presentation(pres_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> PresentationOut:
    pres = db.get(Presentation, pres_id)
    if not pres or (pres.deleted_at is not None):
        raise HTTPException(status_code=404, detail="文件不存在")
    if not can_access(user, pres):
        raise HTTPException(status_code=403, detail="无权访问该文件(私有)")
    progress_map: dict[str, Job] = {}
    if pres.current_version_id:
        cur = _current_status_of(db, pres)
        if cur in PROCESSING_STATUSES:
            progress_map = _latest_jobs_for_versions(db, [pres.current_version_id])
    return _presentation_to_out(db, pres, progress_map)


@router.delete("/presentations/{pres_id}")
def delete_presentation(pres_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not can_modify(user, pres):
        raise HTTPException(status_code=403, detail="无权删除该文件(仅 owner 或管理员)")
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
    if not can_modify(user, pres):
        raise HTTPException(status_code=403, detail="无权恢复该文件")
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
    if not can_modify(user, pres):
        raise HTTPException(status_code=403, detail="无权重解析该文件")
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
    """全库页面瀑布流(当前版本,未删除)。按可见性过滤(超管看全部;普通看 team + 自己)。"""
    storage = get_storage()
    base_q = (
        db.query(Slide, Presentation.title.label("pres_title"))
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(Presentation.current_version_id == PresentationVersion.id)
    )
    if not user.is_superuser:
        base_q = base_q.filter(or_(
            Presentation.visibility == "team",
            Presentation.owner_id == user.id,
        ))
    rows = (
        base_q
        .order_by(Presentation.created_at.desc(), Slide.page_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = []
    fav_ids = favorite_slide_ids(db, user.id, [s.id for s, _ in rows])
    for s, pres_title in rows:
        prev = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append(SlideOut.from_model(s, preview_url=prev, thumbnail_url=thumb,
                                       presentation_title=pres_title, is_favorite=s.id in fav_ids))
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
    if not can_access(user, pres):
        raise HTTPException(status_code=403, detail="无权访问该文件(私有)")
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
    fav_ids = favorite_slide_ids(db, user.id, [s.id for s in slides])
    for s in slides:
        prev_url = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb_url = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append(SlideOut.from_model(s, preview_url=prev_url, thumbnail_url=thumb_url,
                                       presentation_title=pres.title, is_favorite=s.id in fav_ids))
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
    if pres and not can_access(user, pres):
        raise HTTPException(status_code=403, detail="无权访问该页面(私有文件)")
    return SlideDetail(
        id=s.id, version_id=s.version_id, page_no=s.page_no, title=s.title,
        native_text=s.native_text, notes_text=s.notes_text, manual_summary=s.manual_summary,
        ai_summary=s.ai_summary, preview_object_key=s.preview_object_key,
        thumbnail_object_key=s.thumbnail_object_key, parse_status=s.parse_status,
        user_note=s.user_note, fingerprint=s.fingerprint,
        preview_url=prev_url, thumbnail_url=thumb_url,
        content_json=s.content_json, presentation_title=pres.title if pres else None,
        mineru_markdown=s.mineru_markdown,
        is_favorite=is_favorite(db, user.id, s.id),
        source_format=getattr(version, "source_format", "pptx") or "pptx" if version else "pptx",
    )


@router.patch("/slides/{slide_id}", response_model=SlideOut)
def patch_slide(slide_id: str, body: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> SlideOut:
    s = db.get(Slide, slide_id)
    if not s:
        raise HTTPException(status_code=404, detail="页面不存在")
    # 权限:需能修改所属 presentation
    _ver = db.get(PresentationVersion, s.version_id)
    _pres = db.get(Presentation, _ver.presentation_id) if _ver else None
    if _pres and not can_modify(user, _pres):
        raise HTTPException(status_code=403, detail="无权编辑该页面")
    allowed = {"title", "manual_summary", "user_note"}
    for k, v in body.items():
        if k in allowed:
            setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return SlideOut.from_model(s)


@router.post("/presentations/{pres_id}/versions/{vid}/set-current")
def set_current_version(pres_id: str, vid: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    """切换当前版本(PRD §10.4)。"""
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(404, "文件不存在")
    if not can_modify(user, pres):
        raise HTTPException(403, "无权切换该文件版本")
    version = db.get(PresentationVersion, vid)
    if not version or version.presentation_id != pres_id:
        raise HTTPException(400, "版本不属于该文件")
    pres.current_version_id = vid
    db.commit()
    return {"detail": f"已切换当前版本为 v{version.version_no}"}


@router.post("/slides/{slide_id}/exports/pptx")
def export_slide(slide_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> dict:
    """触发单页 PPTX 导出(ADR-0002),返回导出任务结果。
    仅 .pptx 源可用(依赖 Open XML 关系图);ppt/pdf 无可拆部件 → 400。"""
    slide = db.get(Slide, slide_id)
    if not slide:
        raise HTTPException(404, "页面不存在")
    # 权限:能访问所属 presentation
    _ver = db.get(PresentationVersion, slide.version_id) if slide.version_id else None
    _pres = db.get(Presentation, _ver.presentation_id) if _ver else None
    if _pres and not can_access(user, _pres):
        raise HTTPException(status_code=403, detail="无权导出该页面(私有)")
    # 格式门控:非 pptx 不支持单页导出
    version = db.get(PresentationVersion, slide.version_id) if slide.version_id else None
    src_fmt = getattr(version, "source_format", "pptx") if version else "pptx"
    if src_fmt != "pptx":
        raise HTTPException(400, f"单页 PPTX 导出仅支持 .pptx 源(当前为 .{src_fmt})")
    from app.tasks.export import export_single_slide_task
    # 同步等待结果(导出较快,结构遍历 + 存储约 1-2s)
    res = export_single_slide_task.apply(args=[slide_id]).get(timeout=120)
    if not res.get("object_key"):
        raise HTTPException(400, res.get("error") or "导出失败")
    # 返回签名下载 URL
    storage = get_storage()
    url = storage.presigned_get_url(res["object_key"], expires=3600)
    return {"status": res["status"], "download_url": url, "object_key": res["object_key"]}


@router.get("/presentations/{pres_id}/version-diff")
def version_diff(pres_id: str, from_vid: str = Query(...), to_vid: str = Query(...),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """版本间页面差异(ADR-0008 §2)。返回各 match_type 的统计与明细。"""
    from app.models import VersionSlideMatch
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(404, "文件不存在")
    if not can_access(user, pres):
        raise HTTPException(status_code=403, detail="无权查看该文件")
    rows = db.query(VersionSlideMatch).filter(
        VersionSlideMatch.from_version_id == from_vid,
        VersionSlideMatch.to_version_id == to_vid,
    ).all()
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r.match_type, []).append({
            "from_slide_id": r.from_slide_id, "to_slide_id": r.to_slide_id,
            "score": r.score,
        })
    return {
        "summary": {k: len(v) for k, v in groups.items()},
        "details": groups,
    }


@router.get("/presentations/{pres_id}/download-source")
def download_source(pres_id: str, version_id: str | None = Query(None),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not can_access(user, pres):
        raise HTTPException(status_code=403, detail="无权下载该文件(私有)")
    vid = version_id or pres.current_version_id
    version = db.get(PresentationVersion, vid)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    storage = get_storage()
    data = storage.get_object(version.source_object_key)
    src_fmt = getattr(version, "source_format", "pptx") or "pptx"
    mime_map = {
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "pdf": "application/pdf",
    }
    ext = src_fmt if src_fmt in ("pptx", "ppt", "pdf") else "pptx"
    fname = version.original_filename or f"source.{ext}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime_map.get(src_fmt, mime_map["pptx"]),
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ============ 文件管理增强 ============

@router.patch("/presentations/{pres_id}", response_model=PresentationOut)
def patch_presentation(
    pres_id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PresentationOut:
    """重命名 / 移动文件夹 / 切换可见性。仅 owner 或超管。"""
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(404, "文件不存在")
    if not can_modify(user, pres):
        raise HTTPException(403, "无权修改该文件")
    allowed = {"title", "folder_id", "visibility"}
    for k, v in body.items():
        if k == "visibility" and v not in ("team", "private"):
            raise HTTPException(400, "visibility 必须为 team 或 private")
        if k in allowed:
            setattr(pres, k, v)
    db.commit()
    db.refresh(pres)
    return _presentation_to_out(db, pres)


@router.post("/presentations/batch")
def batch_presentations(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """批量操作:ids + action(delete 软删 / reparse 重新解析)。仅操作有权访问的。"""
    from datetime import datetime, timezone
    ids = body.get("ids") or []
    action = body.get("action")
    if action not in ("delete", "reparse"):
        raise HTTPException(400, "action 必须为 delete 或 reparse")
    if not ids:
        raise HTTPException(400, "ids 不能为空")
    items = db.query(Presentation).filter(Presentation.id.in_(ids)).all()
    done = 0
    for pres in items:
        if not can_modify(user, pres):
            continue
        if action == "delete":
            if pres.deleted_at is None:
                pres.deleted_at = datetime.now(timezone.utc)
                done += 1
        elif action == "reparse":
            version = db.get(PresentationVersion, pres.current_version_id) if pres.current_version_id else None
            if version and version.status in ("BASIC_READY", "ENRICHED", "READY", "PARSED", "RENDERING", "PARTIAL_FAILED"):
                try:
                    db.query(Job).filter(
                        Job.target_id == version.id, Job.job_type == "parse_mineru"
                    ).update({Job.status: "pending"}, synchronize_session=False)
                    from app.tasks.mineru import parse_mineru_task
                    parse_mineru_task.delay(version.id)
                    done += 1
                except Exception:
                    pass
    db.commit()
    return {"detail": f"已处理 {done} 个文件", "processed": done}


# ============ 回收站:永久删除 + 清空 ============

def _hard_delete_presentation(db: Session, pres: Presentation) -> None:
    """硬删:清 MinIO 对象 + CASCADE DB 关联 + 删 Presentation。"""
    storage = get_storage()
    # 1. 清 MinIO 对象(整个 presentation 前缀)
    storage.delete_by_prefix(f"presentations/{pres.id}/")
    # 2. 删 DB 关联(FK 无 ON DELETE CASCADE,显式删)
    versions = db.query(PresentationVersion).filter(PresentationVersion.presentation_id == pres.id).all()
    version_ids = [v.id for v in versions]
    slide_ids = [s.id for s in db.query(Slide).filter(Slide.version_id.in_(version_ids)).all()] if version_ids else []
    if slide_ids:
        db.query(SlideTag).filter(SlideTag.slide_id.in_(slide_ids)).delete(synchronize_session=False)
        db.query(Favorite).filter(Favorite.slide_id.in_(slide_ids)).delete(synchronize_session=False)
        db.query(VersionSlideMatch).filter(
            or_(VersionSlideMatch.from_slide_id.in_(slide_ids), VersionSlideMatch.to_slide_id.in_(slide_ids))
        ).delete(synchronize_session=False)
    db.query(Slide).filter(Slide.version_id.in_(version_ids)).delete(synchronize_session=False) if version_ids else None
    db.query(Job).filter(Job.target_id.in_(version_ids)).delete(synchronize_session=False) if version_ids else None
    db.query(PresentationVersion).filter(PresentationVersion.presentation_id == pres.id).delete(synchronize_session=False)
    db.delete(pres)
    db.commit()


@router.delete("/presentations/{pres_id}/permanent")
def permanent_delete(pres_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> dict:
    """永久删除(硬删 DB + 清 MinIO,不可恢复)。仅 owner 或超管。"""
    pres = db.get(Presentation, pres_id)
    if not pres:
        raise HTTPException(404, "文件不存在")
    if not can_modify(user, pres):
        raise HTTPException(403, "无权永久删除该文件")
    _hard_delete_presentation(db, pres)
    return {"detail": "已永久删除(对象存储已清理)"}


@router.delete("/trash/empty")
def empty_trash(db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> dict:
    """清空回收站。超管清全部已删除;普通用户仅清自己的(owner_id)。"""
    q = db.query(Presentation).filter(Presentation.deleted_at.is_not(None))
    if not user.is_superuser:
        q = q.filter(Presentation.owner_id == user.id)
    items = q.all()
    for pres in items:
        _hard_delete_presentation(db, pres)
    return {"detail": f"已清空回收站({len(items)} 个文件)"}
