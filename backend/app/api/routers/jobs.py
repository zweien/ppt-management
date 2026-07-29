"""Jobs 路由(任务中心, §15 / §5.1)。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Job, User
from app.schemas.presentation import JobOut
from app.services.jobs import find_or_create_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


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
    return [JobOut(
        id=j.id, job_type=j.job_type, target_type=j.target_type, target_id=j.target_id,
        status=j.status, progress=j.progress, error_code=j.error_code,
        error_message=j.error_message, stage=j.stage, started_at=j.started_at,
        finished_at=j.finished_at, created_at=j.created_at,
    ) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> JobOut:
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobOut(
        id=j.id, job_type=j.job_type, target_type=j.target_type, target_id=j.target_id,
        status=j.status, progress=j.progress, error_code=j.error_code,
        error_message=j.error_message, stage=j.stage, started_at=j.started_at,
        finished_at=j.finished_at, created_at=j.created_at,
    )


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
    return JobOut(
        id=j.id, job_type=j.job_type, target_type=j.target_type, target_id=j.target_id,
        status=j.status, progress=j.progress, error_code=j.error_code,
        error_message=j.error_message, stage=j.stage, started_at=j.started_at,
        finished_at=j.finished_at, created_at=j.created_at,
    )


def _dispatch_retry(job: Job) -> None:
    """Re-dispatch the celery task for a retried job."""
    try:
        if job.job_type == "parse_openxml":
            from app.tasks.basic import parse_openxml_task
            parse_openxml_task.delay(job.target_id)
        elif job.job_type == "render_preview":
            from app.tasks.render import render_preview_task
            render_preview_task.delay(job.target_id)
    except Exception:
        # If broker unavailable, the job stays pending; worker will pick up if re-enqueued elsewhere
        pass
