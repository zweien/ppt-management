"""Auth router:OIDC(SSO)登录 / 回调 / me / 登出。

流程(Authentik Authorization Code,后端代理):
- GET /api/auth/login       → 302 到 Authentik authorize(state 防 CSRF)
- GET /api/auth/callback    → 验证 state → code 换 token → userinfo → get-or-create User
                              → set session cookie → 302 回前端
- GET /api/auth/me          → 当前用户(从 session)
- GET /api/auth/logout      → 清 session cookie + 302 到 Authentik end-session

非 SSO 模式(OIDC_ENABLED=false)保留密码登录 fallback。
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
    UserOut,
    UserOutResolver,
)
from app.services import oidc
from app.services.session import create_session, read_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = settings.SESSION_COOKIE_NAME


def _set_session_cookie(resp: RedirectResponse | Response, user_id: str) -> None:
    token = create_session(user_id)
    # SameSite=Lax:允许顶层导航回调带 cookie;本机 http 不设 Secure。
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(resp: RedirectResponse) -> None:
    resp.delete_cookie(SESSION_COOKIE, path="/")


def _get_or_create_user(db: Session, info: dict) -> User:
    """按 Authentik subject(external_id)查;无则创建。同步 is_superuser / email。"""
    sub = info.get("sub")
    if not sub:
        raise oidc.OIDCError("userinfo 缺少 sub")
    username = info.get("preferred_username") or info.get("email") or f"sso-{sub[:8]}"
    email = info.get("email")
    display = info.get("name") or info.get("nickname") or username
    is_super = oidc.is_superuser_from_groups(info.get("groups"))

    user = db.query(User).filter(User.external_id == sub).first()
    if user is None:
        # 用户名冲突时加后缀
        base_username = username
        n = 1
        while db.query(User).filter(User.username == username).first() is not None:
            username = f"{base_username}-{n}"
            n += 1
        user = User(
            username=username,
            password_hash=None,
            status="active",
            is_superuser=is_super,
            external_id=sub,
            email=email,
            display_name=display,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 同步:超管/邮箱可能变了
        changed = False
        if user.is_superuser != is_super:
            user.is_superuser = is_super
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if display and user.display_name != display:
            user.display_name = display
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
    return user


# ============ SSO 流程 ============

@router.get("/login")
def sso_login(request: Request):
    """302 到 Authentik authorize。state 存 cookie 防 CSRF。"""
    state = secrets.token_urlsafe(16)
    url = oidc.authorize_url(state)
    resp = RedirectResponse(url)
    # state 用一个短 cookie 校验回调(10 分钟)
    resp.set_cookie("oidc_state", state, max_age=600, httponly=True, samesite="lax", path="/")
    return resp


@router.get("/callback")
def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Authentik 回调:验证 state → 换 token → userinfo → 建 session → 回前端。"""
    if error:
        raise HTTPException(400, f"Authentik 授权失败:{error}")
    if not code or not state:
        raise HTTPException(400, "回调缺少 code/state")

    # 校验 state(防 CSRF)
    cookie_state = request.cookies.get("oidc_state")
    if not cookie_state or cookie_state != state:
        raise HTTPException(400, "state 校验失败(CSRF)")

    try:
        tokens = oidc.exchange_code(code)
        info = oidc.fetch_userinfo(tokens.get("access_token", ""))
    except oidc.OIDCError as e:
        raise HTTPException(400, str(e))

    user = _get_or_create_user(db, info)
    if user.status != "active":
        raise HTTPException(403, "账号已停用")

    resp = RedirectResponse(settings.WEB_BASE_URL or "/")
    _set_session_cookie(resp, user.id)
    resp.delete_cookie("oidc_state", path="/")
    return resp


@router.get("/logout")
def sso_logout(request: Request):
    """清 session cookie + 302 到 Authentik end-session(单点登出)。"""
    post = settings.WEB_BASE_URL or None
    end = oidc.end_session_url(post)
    resp = RedirectResponse(end or settings.WEB_BASE_URL or "/")
    _clear_session_cookie(resp)
    return resp


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOutResolver.from_model(user)


# ============ 非 SSO fallback(OIDC_ENABLED=false 时)============

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if settings.OIDC_ENABLED:
        raise HTTPException(400, "已启用 SSO,请使用 Authentik 登录")
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    token = create_access_token(user.id, extra={"username": user.username})
    return TokenResponse(access_token=token, user=UserOutResolver.from_model(user))


@router.put("/password")
def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if settings.OIDC_ENABLED or not user.password_hash:
        raise HTTPException(400, "SSO 用户不支持修改密码")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.add(user)
    db.commit()
    return {"detail": "密码已修改"}
