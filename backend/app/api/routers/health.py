"""健康检查(PRD §18.3):覆盖 PostgreSQL / Redis / MinIO。"""
import redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.storage import get_storage
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """聚合健康状态。"""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["postgres"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["postgres"] = f"fail: {e}"

    # Redis
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, socket_timeout=2
        )
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis"] = f"fail: {e}"

    # MinIO
    try:
        storage = get_storage()
        storage.ensure_bucket()
        checks["minio"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["minio"] = f"fail: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
