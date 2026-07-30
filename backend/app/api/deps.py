"""FastAPI dependencies."""
from typing import Generator

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.services.session import read_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证或认证已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id: str | None = None

    # SSO 模式:从 session cookie 解析
    if settings.OIDC_ENABLED:
        cookie_val = request.cookies.get(settings.SESSION_COOKIE_NAME)
        user_id = read_session(cookie_val)
    else:
        # 非 SSO fallback:从 Bearer JWT 解析
        if not token:
            raise creds_exc
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
        except Exception:
            raise creds_exc

    if not user_id:
        raise creds_exc
    user = db.get(User, user_id)
    if not user or user.status != "active":
        raise creds_exc
    return user


def require_superuser(user: User = Depends(get_current_user)) -> User:
    """要求当前用户是超级管理员(is_superuser)。用于设置等管理接口。"""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
