"""运行时可调配置(DB 优先 + 进程内存缓存)。

设计:可调配置存 app_settings 表(key→JSON value)。get_setting 优先查 DB,
无记录则回退到 settings(env)默认值(安全降级)。进程内缓存 30s,降低 DB 压力。

api 与 worker 是独立进程,各有自己的缓存;改配置后最多 30s 全进程生效。
设置接口写入后会 invalidate 本进程缓存;跨进程靠 TTL 自然过期。
"""
from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AppSetting

# key -> (expires_at_epoch, value)
_cache: dict[str, tuple[float, Any]] = {}
TTL_SECONDS = 30


def get_setting(key: str, default: Any) -> Any:
    """读取配置:DB 优先(命中缓存走缓存),否则回退 default。返回反序列化后的值。"""
    now = time.time()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    db = SessionLocal()
    try:
        row = db.get(AppSetting, key)
        val = json.loads(row.value) if row else default
    except Exception:
        val = default
    finally:
        db.close()
    _cache[key] = (now + TTL_SECONDS, val)
    return val


def set_setting(key: str, value: Any) -> None:
    """写入配置(upsert)并清本进程缓存。"""
    db = SessionLocal()
    try:
        row = db.get(AppSetting, key)
        serialized = json.dumps(value, ensure_ascii=False)
        if row:
            row.value = serialized
        else:
            row = AppSetting(key=key, value=serialized)
            db.add(row)
        db.commit()
    finally:
        db.close()
    _cache.pop(key, None)


def invalidate(key: str | None = None) -> None:
    """清缓存。key=None 清全部。"""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


# --- 类型化便捷访问器(供各调用点使用) ---

def get_upload_max_size_mb() -> int:
    return int(get_setting("UPLOAD_MAX_SIZE_MB", settings.UPLOAD_MAX_SIZE_MB))


def get_upload_extensions() -> list[str]:
    val = get_setting("UPLOAD_ALLOWED_EXTENSIONS", settings.UPLOAD_ALLOWED_EXTENSIONS)
    return list(val) if isinstance(val, (list, tuple)) else [str(val)]


def get_zip_bomb_ratio() -> int:
    return int(get_setting("ZIP_BOMB_RATIO", settings.ZIP_BOMB_RATIO))


def get_mineru_url() -> str:
    return str(get_setting("MINERU_API_URL", settings.MINERU_API_URL or "http://host.docker.internal:8765"))


def get_embedding_url() -> str:
    return str(get_setting("EMBEDDING_SERVICE_URL", settings.EMBEDDING_SERVICE_URL))


def get_default_embedding_model() -> str:
    return str(get_setting("DEFAULT_EMBEDDING_MODEL", settings.DEFAULT_EMBEDDING_MODEL))


def get_vision_max_long_edge() -> int:
    return int(get_setting("VISION_IMAGE_MAX_LONG_EDGE", settings.VISION_IMAGE_MAX_LONG_EDGE))


def get_token_expire_minutes() -> int:
    return int(get_setting("ACCESS_TOKEN_EXPIRE_MINUTES", settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def get_cors_origins() -> list[str]:
    """CORS 仅启动时读一次(中间件),动态改需重启。这里仍提供以便设置页展示。"""
    val = get_setting("CORS_ORIGINS", settings.CORS_ORIGINS)
    return list(val) if isinstance(val, (list, tuple)) else [str(val)]


# --- UI 配置(品牌 / 外观) ---

def get_app_name() -> str:
    return str(get_setting("APP_DISPLAY_NAME", settings.APP_NAME))


def get_mesh_enabled() -> bool:
    return bool(get_setting("MESH_ENABLED", True))


def get_default_theme() -> str:
    val = str(get_setting("DEFAULT_THEME", "light"))
    return val if val in ("light", "dark") else "light"


def get_logo_object_key() -> str | None:
    """返回当前 logo 的 MinIO object key,未上传时 None。不走缓存(低频且需即时反映)。"""
    db = SessionLocal()
    try:
        row = db.get(AppSetting, "LOGO_OBJECT_KEY")
        return str(row.value).strip('"') if row and row.value else None
    except Exception:
        return None
    finally:
        db.close()


def set_logo_object_key(key: str | None) -> None:
    """记录 logo object key(None 表示移除 logo)。"""
    db = SessionLocal()
    try:
        if key is None:
            row = db.get(AppSetting, "LOGO_OBJECT_KEY")
            if row:
                db.delete(row)
        else:
            row = db.get(AppSetting, "LOGO_OBJECT_KEY")
            if row:
                row.value = json.dumps(key)
            else:
                db.add(AppSetting(key="LOGO_OBJECT_KEY", value=json.dumps(key)))
        db.commit()
    finally:
        db.close()

