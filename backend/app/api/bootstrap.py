"""Bootstrap:创建初始管理员账号(PRD §3.1,单管理员)。

通过环境变量 ADMIN_USERNAME/ADMIN_PASSWORD 创建(不依赖手动 SQL)。
保留 owner_id/created_by/updated_by 字段为后续多人预留(CONTEXT.md)。
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import ModelConfig, User

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


def bootstrap_default_embedding() -> None:
    """创建默认 embedding 模型配置(若尚无 default embedding 配置)。

    ADR-0006/0008:向量检索依赖一条 is_default 的 embedding model_config。
    首次启动时若不存在,用 EMBEDDING_SERVICE_URL / DEFAULT_EMBEDDING_MODEL 注入一条,
    指向宿主机的 OpenAI 兼容 /v1/embeddings 服务(bge-m3)。
    幂等:已存在 default embedding 配置则跳过(不覆盖用户后续手动改动)。
    """
    db: Session = SessionLocal()
    try:
        existing = (
            db.query(ModelConfig)
            .filter(
                ModelConfig.capability == "embedding",
                ModelConfig.is_default.is_(True),
            )
            .first()
        )
        if existing:
            return
        cfg = ModelConfig(
            name=f"bge-m3 (本地)",
            capability="embedding",
            base_url=settings.EMBEDDING_SERVICE_URL,
            model=settings.DEFAULT_EMBEDDING_MODEL,
            is_enabled=True,
            is_default=True,
        )
        db.add(cfg)
        db.commit()
        logger.info(
            "Bootstrapped default embedding config: %s @ %s",
            settings.DEFAULT_EMBEDDING_MODEL,
            settings.EMBEDDING_SERVICE_URL,
        )
    finally:
        db.close()
