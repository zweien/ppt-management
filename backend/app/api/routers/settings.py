"""设置路由(管理员)。业务可调配置 DB 化 + 只读系统信息脱敏展示。"""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_superuser
from app.core.config import settings
from app.core.storage import get_storage, ui_logo_key
from app.db.session import get_db
from app.models import User
from app.services import runtime_config as rc

router = APIRouter(prefix="/api/settings", tags=["settings"])

# 可调配置的元信息:类型 + 校验。前端据此渲染对应控件。
# type: int / str / list_str
FIELD_DEFS = [
    # (key, label, type, group, options?)
    ("UPLOAD_MAX_SIZE_MB", "单文件大小上限(MB)", "int", "upload", None),
    ("UPLOAD_ALLOWED_EXTENSIONS", "允许的扩展名", "list_str", "upload", None),
    ("ZIP_BOMB_RATIO", "ZIP 解压比上限", "int", "upload", None),
    ("MINERU_API_URL", "MinerU 服务地址", "str", "ai", None),
    ("EMBEDDING_SERVICE_URL", "Embedding 服务地址", "str", "ai", None),
    ("DEFAULT_EMBEDDING_MODEL", "默认 Embedding 模型", "str", "ai", None),
    ("VISION_IMAGE_MAX_LONG_EDGE", "视觉分析图片长边上限(px)", "int", "ai", None),
    ("ACCESS_TOKEN_EXPIRE_MINUTES", "Token 有效期(分钟)", "int", "access", None),
    ("CORS_ORIGINS", "CORS 允许的来源", "list_str", "access", None),
    # UI 配置(APP_DISPLAY_NAME 避免与 APP_NAME env 冲突)
    ("APP_DISPLAY_NAME", "系统名称", "str", "ui", None),
    ("MESH_ENABLED", "Mesh 渐变背景", "bool", "ui", None),
    ("DEFAULT_THEME", "默认主题", "select_str", "ui", ["light", "dark"]),
]

# 分区标签
GROUP_LABELS = {
    "ui": "界面",
    "upload": "上传与安全",
    "ai": "AI 服务",
    "access": "访问与安全",
}


def _current_value(key: str):
    """读取某配置当前生效值(走 runtime_config 的缓存/便捷函数)。"""
    getters = {
        "UPLOAD_MAX_SIZE_MB": rc.get_upload_max_size_mb,
        "UPLOAD_ALLOWED_EXTENSIONS": rc.get_upload_extensions,
        "ZIP_BOMB_RATIO": rc.get_zip_bomb_ratio,
        "MINERU_API_URL": rc.get_mineru_url,
        "EMBEDDING_SERVICE_URL": rc.get_embedding_url,
        "DEFAULT_EMBEDDING_MODEL": rc.get_default_embedding_model,
        "VISION_IMAGE_MAX_LONG_EDGE": rc.get_vision_max_long_edge,
        "ACCESS_TOKEN_EXPIRE_MINUTES": rc.get_token_expire_minutes,
        "CORS_ORIGINS": rc.get_cors_origins,
        "APP_DISPLAY_NAME": rc.get_app_name,
        "MESH_ENABLED": rc.get_mesh_enabled,
        "DEFAULT_THEME": rc.get_default_theme,
    }
    return getters[key]()


def _validate_value(key: str, ftype: str, value, options=None):
    """类型转换 + 基本合法性校验。返回转换后的值,或抛 HTTPException(400)。"""
    try:
        if ftype == "int":
            v = int(value)
            if v <= 0:
                raise ValueError("必须为正整数")
            return v
        if ftype == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in ("true", "1", "yes", "on")
            return bool(value)
        if ftype in ("str", "select_str"):
            v = str(value).strip()
            if not v:
                raise ValueError("不能为空")
            if ftype == "select_str" and options and v not in options:
                raise ValueError(f"必须为 {options} 之一")
            return v
        if ftype == "list_str":
            if isinstance(value, str):
                items = [s.strip() for s in value.split(",") if s.strip()]
            elif isinstance(value, (list, tuple)):
                items = [str(s).strip() for s in value if str(s).strip()]
            else:
                raise ValueError("需为字符串列表")
            if not items:
                raise ValueError("列表不能为空")
            return items
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"{key} 校验失败:{e}")
    raise HTTPException(status_code=400, detail=f"{key} 未知类型 {ftype}")


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_superuser),
) -> dict:
    """返回可调配置(按分区)+ 只读系统信息(脱敏)。"""
    groups: dict[str, list] = {}
    for key, label, ftype, group, options in FIELD_DEFS:
        groups.setdefault(group, []).append({
            "key": key,
            "label": label,
            "type": ftype,
            "value": _current_value(key),
            "options": options,
            # CORS 仅启动时生效
            "restart_required": key == "CORS_ORIGINS",
        })

    return {
        "groups": [
            {"key": g, "label": GROUP_LABELS[g], "fields": fields}
            for g, fields in groups.items()
        ],
        # 只读系统信息(脱敏)
        "system_info": _system_info(),
    }


@router.patch("")
def update_settings(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_superuser),
) -> dict:
    """批量更新可调配置。写入 DB + 清缓存(本进程立即生效;跨进程 ≤30s)。"""
    defs = {k: (ftype, opts) for k, _, ftype, _, opts in FIELD_DEFS}
    updated = []
    for key, value in body.items():
        if key not in defs:
            raise HTTPException(status_code=400, detail=f"未知配置项:{key}")
        ftype, opts = defs[key]
        converted = _validate_value(key, ftype, value, opts)
        rc.set_setting(key, converted)
        updated.append(key)
    return {"detail": f"已更新 {len(updated)} 项", "updated": updated}


# --- Logo(品牌图片,MinIO 存储 + 代理流式返回) ---

LOGO_ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
LOGO_CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
}
LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2MB


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_superuser),
) -> dict:
    """上传品牌 logo(管理员)。存 MinIO,记录 object_key。"""
    filename = (file.filename or "logo.png").lower()
    ext = filename[filename.rfind("."):] if "." in filename else ""
    if ext not in LOGO_ALLOWED:
        raise HTTPException(400, f"不支持的图片类型,允许:{','.join(sorted(LOGO_ALLOWED))}")
    content = await file.read()
    if len(content) > LOGO_MAX_BYTES:
        raise HTTPException(400, f"logo 过大({len(content)} 字节),上限 2MB")
    key = ui_logo_key(ext)
    storage = get_storage()
    storage.put_object(key, content, content_type=LOGO_CONTENT_TYPES.get(ext, "application/octet-stream"))
    rc.set_logo_object_key(key)
    return {"detail": "logo 已更新", "logo_url": "/api/settings/logo"}


@router.delete("/logo")
def remove_logo(
    db: Session = Depends(get_db),
    user: User = Depends(require_superuser),
) -> dict:
    """移除品牌 logo(回退 mesh 方块)。"""
    rc.set_logo_object_key(None)
    return {"detail": "logo 已移除"}


@router.get("/logo")
def get_logo(
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """流式返回 logo 图片(无需认证 — 品牌图,登录页等未登录场景也要展示)。
    URL 固定不失效。无 logo 返回 404。"""
    key = rc.get_logo_object_key()
    if not key:
        raise HTTPException(404, "未设置 logo")
    storage = get_storage()
    try:
        data = storage.get_object(key)
    except Exception:
        raise HTTPException(404, "logo 对象不存在")
    ext = key[key.rfind("."):] if "." in key else ""
    media = LOGO_CONTENT_TYPES.get(ext, "image/png")
    return StreamingResponse(io.BytesIO(data), media_type=media)


def _mask_secret(val: str | None) -> str:
    """脱敏:显示 **** + 末4位。空值显示 -(未设)。"""
    if not val:
        return "-"
    if len(val) <= 4:
        return "****"
    return f"****{val[-4:]}"


def _system_info() -> dict:
    """只读展示当前 env 运行配置(脱敏)。便于管理员排查。"""
    return {
        "应用": {
            "APP_NAME": settings.APP_NAME,
            "APP_VERSION": settings.APP_VERSION,
            "ENV": settings.ENV,
        },
        "数据库": {
            "POSTGRES_HOST": settings.POSTGRES_HOST,
            "POSTGRES_DB": settings.POSTGRES_DB,
            "POSTGRES_USER": settings.POSTGRES_USER,
            "POSTGRES_PASSWORD": _mask_secret(settings.POSTGRES_PASSWORD),
        },
        "对象存储": {
            "MINIO_ENDPOINT": settings.MINIO_ENDPOINT,
            "MINIO_BUCKET": settings.MINIO_BUCKET,
            "MINIO_ACCESS_KEY": _mask_secret(settings.MINIO_ACCESS_KEY),
            "MINIO_SECRET_KEY": _mask_secret(settings.MINIO_SECRET_KEY),
        },
        "安全": {
            "SECRET_KEY": _mask_secret(settings.SECRET_KEY),
            "APP_ENCRYPTION_KEY": _mask_secret(settings.APP_ENCRYPTION_KEY),
            "ADMIN_USERNAME": settings.ADMIN_USERNAME,
            "ADMIN_PASSWORD": _mask_secret(settings.ADMIN_PASSWORD),
        },
    }
