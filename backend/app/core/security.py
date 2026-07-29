"""安全工具:密码哈希(Argon2id)与 JWT(ADR-0001 / §18.1)。"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Argon2id preferred (PRD §18.1); bcrypt as fallback
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    from app.services.runtime_config import get_token_expire_minutes
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=get_token_expire_minutes())
    payload: dict[str, Any] = {"sub": str(subject), "iat": now, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
