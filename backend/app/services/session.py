"""Session cookie:signed(itsdangerous),httpOnly。

payload = user_id;签名 + 过期校验。cookie 名/有效期来自 settings。
"""
from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

_serializer: URLSafeTimedSerializer | None = None


def _serializer_get() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        secret = settings.SESSION_SECRET or settings.SECRET_KEY
        _serializer = URLSafeTimedSerializer(secret, salt="ppt-session")
    return _serializer


def create_session(user_id: str) -> str:
    """签发 session token(放 cookie 值)。"""
    return _serializer_get().dumps(user_id)


def read_session(token: str | None) -> str | None:
    """校验并读取 user_id。无效/过期返回 None。"""
    if not token:
        return None
    try:
        return _serializer_get().loads(token, max_age=settings.SESSION_MAX_AGE)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
