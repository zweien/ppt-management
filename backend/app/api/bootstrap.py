"""Bootstrap:创建初始管理员账号(PRD §3.1,单管理员)。

通过环境变量 ADMIN_USERNAME/ADMIN_PASSWORD 创建(不依赖手动 SQL)。
保留 owner_id/created_by/updated_by 字段为后续多人预留(CONTEXT.md)。
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    """创建初始管理员账号(若不存在)。"""
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if existing:
            return
        user = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            status="active",
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        logger.info("Bootstrapped admin user %r", settings.ADMIN_USERNAME)
    finally:
        db.close()
