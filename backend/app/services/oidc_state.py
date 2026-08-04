"""OIDC state 服务端存储(SE-07):Redis + 10 分钟 TTL,替代 cookie 方案。

问题:cookie 方案在「发起登录 host ≠ 回调 host」时失败(如从 localhost 发起,
Authentik 按 OIDC_REDIRECT_URI 回调到 192.168.x.x,cookie 不跨 host)。
服务端存储对 host 无感:state 一次有效,回调校验后即删。
"""
from __future__ import annotations

import logging

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600  # 10 分钟,与原 cookie max_age 一致
_KEY_PREFIX = "oidc:state:"

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_timeout=3,
            decode_responses=True,
        )
    return _client


def store_state(state: str) -> None:
    """存储 state(10 分钟有效)。"""
    try:
        _redis().setex(f"{_KEY_PREFIX}{state}", _TTL_SECONDS, "1")
    except Exception as e:  # noqa: BLE001
        logger.warning("oidc state store failed (redis): %s", e)


def consume_state(state: str) -> bool:
    """校验并消费 state(一次性)。存在则删除并返回 True。"""
    try:
        return _redis().delete(f"{_KEY_PREFIX}{state}") == 1
    except Exception as e:  # noqa: BLE001
        logger.warning("oidc state consume failed (redis): %s", e)
        return False
