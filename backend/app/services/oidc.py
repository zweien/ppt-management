"""OIDC 客户端(Authentik):discovery / authorize URL / code 交换 / userinfo。

后端代理 Authorization Code flow:前端跳转 login → Authentik 回调 →
后端用 code 换 token + 拉 userinfo → 建 session。
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

# discovery 缓存(进程内,TTL 10 分钟)
_discovery_cache: dict[str, Any] = {}
_discovery_ts: float = 0.0
_DISCOVERY_TTL = 600


class OIDCError(Exception):
    """OIDC 流程错误(配置缺失 / 网络失败 / token 无效)。"""


def _internal_issuer() -> str:
    """后端容器内访问 issuer 的地址(discovery/token/userinfo,服务端调用)。"""
    return (settings.OIDC_INTERNAL_ISSUER or settings.OIDC_ISSUER).rstrip("/")


def _external_issuer() -> str:
    """浏览器访问 issuer 的地址(authorize/end-session 跳转)。"""
    return settings.OIDC_ISSUER.rstrip("/")


def _to_external(url: str) -> str:
    """把 discovery 返回的 internal URL 改写为浏览器可访问的 external host。
    discovery 来自 OIDC_INTERNAL_ISSUER(host.docker.internal),浏览器需 localhost。"""
    if not url:
        return url
    try:
        from urllib.parse import urlsplit, urlunsplit
        ext = urlsplit(_external_issuer())
        parts = urlsplit(url)
        return urlunsplit((parts.scheme or ext.scheme, ext.netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def get_discovery() -> dict[str, Any]:
    """拉取 issuer 的 OIDC discovery 文档(缓存 10 分钟)。"""
    global _discovery_ts, _discovery_cache
    if _discovery_cache and time.time() - _discovery_ts < _DISCOVERY_TTL:
        return _discovery_cache
    url = f"{_internal_issuer()}/.well-known/openid-configuration"
    try:
        r = httpx.get(url, timeout=10.0, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise OIDCError(f"无法获取 OIDC discovery({url}):{e}") from e
    _discovery_cache = data
    _discovery_ts = time.time()
    return data


def authorize_url(state: str) -> str:
    """构造 Authentik authorize URL(前端/后端 302 到此;浏览器可访问)。"""
    disc = get_discovery()
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.OIDC_SCOPES,
        "state": state,
    }
    return f"{_to_external(disc['authorization_endpoint'])}?{urlencode(params)}"


def end_session_url(post_logout_redirect: str | None = None) -> str:
    """Authentik end-session URL(单点登出;浏览器可访问)。"""
    disc = get_discovery()
    base = disc.get("end_session_endpoint")
    if not base:
        return ""
    base = _to_external(base)
    if post_logout_redirect:
        return f"{base}?{urlencode({'post_logout_redirect_uri': post_logout_redirect})}"
    return base


def exchange_code(code: str) -> dict[str, Any]:
    """用 authorization code 换 token(access_token / id_token / refresh_token)。"""
    disc = get_discovery()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "client_id": settings.OIDC_CLIENT_ID,
        "client_secret": settings.OIDC_CLIENT_SECRET,
    }
    try:
        r = httpx.post(disc["token_endpoint"], data=data, timeout=15.0, verify=False)
        if r.status_code >= 400:
            raise OIDCError(f"token 交换失败({r.status_code}):{r.text[:300]}")
        return r.json()
    except httpx.HTTPError as e:
        raise OIDCError(f"token 交换网络错误:{e}") from e


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    """用 access_token 拉 userinfo(sub / preferred_username / email / groups)。"""
    disc = get_discovery()
    try:
        r = httpx.get(
            disc["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
            verify=False,
        )
        if r.status_code >= 400:
            raise OIDCError(f"userinfo 失败({r.status_code}):{r.text[:300]}")
        return r.json()
    except httpx.HTTPError as e:
        raise OIDCError(f"userinfo 网络错误:{e}") from e


def is_superuser_from_groups(groups: Any) -> bool:
    """按配置的超管组名判定。groups 可能是 list 或含 groups 字段的对象。"""
    target = settings.OIDC_SUPERUSER_GROUP
    if not target:
        return False
    # Authentik userinfo 的 groups 通常是 list[str](组名或 DN)
    if isinstance(groups, list):
        for g in groups:
            gname = g.split(",")[0].split("=")[-1] if isinstance(g, str) else str(g)
            if gname == target or g == target:
                return True
    return False
