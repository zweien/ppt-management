"""Jobs 路由(任务中心, §15 / §5.1)。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Job, Presentation, PresentationVersion, Slide, User
from app.schemas.presentation import JobOut
from app.services.jobs import find_or_create_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_jobout(
    j: Job,
    version_map: dict[str, PresentationVersion] | None = None,
    slide_map: dict[str, Slide] | None = None,
    pres_map: dict[str, Presentation] | None = None,
) -> JobOut:
    """Build a JobOut, optionally filling target display info from pre-fetched
    maps. When maps are None the three target_* fields fall back to None."""
    target_name: str | None = None
    target_parent_name: str | None = None
    target_page_no: int | None = None

    if j.target_type == "version" and version_map is not None:
        v = version_map.get(j.target_id)
        if v is not None:
            target_name = v.original_filename or None
            if pres_map is not None:
                p = pres_map.get(v.presentation_id)
                if p is not None:
                    target_parent_name = p.title
    elif j.target_type == "slide" and slide_map is not None:
        s = slide_map.get(j.target_id)
        if s is not None:
            target_name = s.title or None
            target_page_no = s.page_no
            if version_map is not None and pres_map is not None:
                v = version_map.get(s.version_id)
                if v is not None:
                    p = pres_map.get(v.presentation_id)
                    if p is not None:
                        target_parent_name = p.title

    return JobOut(
        id=j.id, job_type=j.job_type, target_type=j.target_type, target_id=j.target_id,
        status=j.status, progress=j.progress, error_code=j.error_code,
        error_message=j.error_message, stage=j.stage, started_at=j.started_at,
        finished_at=j.finished_at, created_at=j.created_at,
        target_name=target_name, target_parent_name=target_parent_name,
        target_page_no=target_page_no,
    )


def _resolve_targets(db: Session, jobs: list[Job]) -> tuple[dict, dict, dict]:
    """Batch-fetch version/slide/presentation rows for the given jobs to avoid
    N+1. Returns (version_map, slide_map, pres_map) keyed by id."""
    version_ids = {j.target_id for j in jobs if j.target_type == "version"}
    slide_ids = {j.target_id for j in jobs if j.target_type == "slide"}

    version_map: dict[str, PresentationVersion] = {}
    slide_map: dict[str, Slide] = {}
    pres_ids: set[str] = set()

    if version_ids:
        for v in db.query(PresentationVersion).filter(
            PresentationVersion.id.in_(version_ids)
        ).all():
            version_map[v.id] = v
            pres_ids.add(v.presentation_id)
    # Slides need their parent version → presentation, so also fetch those versions.
    if slide_ids:
        for s in db.query(Slide).filter(Slide.id.in_(slide_ids)).all():
            slide_map[s.id] = s
            pres_ids_versions = {s.version_id for s in slide_map.values()}
            # Fetch versions not already loaded.
            missing = pres_ids_versions - set(version_map.keys())
            if missing:
                for v in db.query(PresentationVersion).filter(
                    PresentationVersion.id.in_(missing)
                ).all():
                    version_map[v.id] = v
                    pres_ids.add(v.presentation_id)
            else:
                for vid in pres_ids_versions:
                    v = version_map.get(vid)
                    if v is not None:
                        pres_ids.add(v.presentation_id)

    pres_map: dict[str, Presentation] = {}
    if pres_ids:
        for p in db.query(Presentation).filter(Presentation.id.in_(pres_ids)).all():
            pres_map[p.id] = p

    return version_map, slide_map, pres_map


@router.get("", response_model=list[JobOut])
def list_jobs(
    target_id: str | None = Query(None),
    job_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobOut]:
    q = db.query(Job)
    if target_id:
        q = q.filter(Job.target_id == target_id)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    if status_filter:
        q = q.filter(Job.status == status_filter)
    jobs = q.order_by(Job.created_at.desc()).limit(limit).all()
    version_map, slide_map, pres_map = _resolve_targets(db, jobs)
    return [_to_jobout(j, version_map, slide_map, pres_map) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> JobOut:
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="任务不存在")
    version_map, slide_map, pres_map = _resolve_targets(db, [j])
    return _to_jobout(j, version_map, slide_map, pres_map)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> JobOut:
    """对失败任务单独重试(§15.3 幂等)。"""
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="任务不存在")
    if j.status != "failed":
        raise HTTPException(status_code=400, detail="仅失败任务可重试")
    # Reset and re-dispatch based on job type
    j.status = "pending"
    j.error_code = None
    j.error_message = None
    j.started_at = None
    j.finished_at = None
    j.progress = 0
    db.commit()
    db.refresh(j)
    # Re-trigger the actual task (lazy import to avoid circular)
    _dispatch_retry(j)
    version_map, slide_map, pres_map = _resolve_targets(db, [j])
    return _to_jobout(j, version_map, slide_map, pres_map)


def _dispatch_retry(job: Job) -> None:
    """Re-dispatch the celery task for a retried job."""
    try:
        if job.job_type == "parse_openxml":
            from app.tasks.basic import parse_openxml_task
            parse_openxml_task.delay(job.target_id)
        elif job.job_type == "render_preview":
            from app.tasks.render import render_preview_task
            render_preview_task.delay(job.target_id)
        elif job.job_type == "parse_mineru":
            from app.tasks.mineru import parse_mineru_task
            parse_mineru_task.delay(job.target_id)
        elif job.job_type == "analyze_visual":
            from app.tasks.ai import analyze_visual_task
            analyze_visual_task.delay(job.target_id)
        elif job.job_type == "build_embedding":
            from app.tasks.ai import build_embedding_task
            build_embedding_task.delay(job.target_id)
    except Exception:
        # If broker unavailable, the job stays pending; worker will pick up if re-enqueued elsewhere
        pass
