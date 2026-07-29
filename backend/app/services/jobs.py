"""Job 服务:创建/查询任务,幂等键,状态推进(PRD §15)。"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Job


def make_idempotency_key(job_type: str, target_id: str, input_data: str | None = None) -> str:
    h = hashlib.sha256()
    h.update(job_type.encode())
    h.update(b"|")
    h.update(target_id.encode())
    if input_data:
        h.update(b"|")
        h.update(input_data.encode())
    return f"{job_type}:{target_id}:{h.hexdigest()[:16]}"


def find_or_create_job(
    db: Session,
    job_type: str,
    target_type: str,
    target_id: str,
    stage: str | None = None,
    input_data: str | None = None,
) -> Job:
    """幂等:相同 idempotency_key 的 job 直接返回已有的,不重复创建(§15.3)。"""
    key = make_idempotency_key(job_type, target_id, input_data)
    existing = db.query(Job).filter(Job.idempotency_key == key).first()
    if existing:
        return existing
    job = Job(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        status="pending",
        progress=0,
        stage=stage,
        idempotency_key=key,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_running(db: Session, job: Job) -> None:
    if job.status not in ("running", "success"):
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()


def mark_success(db: Session, job: Job) -> None:
    job.status = "success"
    job.progress = 100
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def mark_failed(
    db: Session, job: Job, error_code: str, error_message: str, log_ref: str | None = None
) -> None:
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message
    job.finished_at = datetime.now(timezone.utc)
    if log_ref:
        job.log_ref = log_ref
    db.commit()
