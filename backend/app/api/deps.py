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

    # 机器认证优先:X-API-Key(SE-06,AI agent 调开放接口)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        from app.services.api_keys import verify_api_key
        key_user = verify_api_key(db, api_key)
        if key_user and key_user.status == "active":
            return key_user
        raise creds_exc

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


def can_access(user: User, presentation) -> bool:
    """判断用户能否访问某 presentation(team 共享 或 自己的 private 或 超管)。"""
    if user.is_superuser:
        return True
    if presentation.visibility == "team":
        return True
    return presentation.owner_id == user.id


def can_modify(user: User, presentation) -> bool:
    """判断用户能否修改/删除某 presentation(owner 自己 或 超管)。
    team 文件任何登录用户可浏览,但改/删仍限 owner/super。"""
    if user.is_superuser:
        return True
    return presentation.owner_id == user.id
