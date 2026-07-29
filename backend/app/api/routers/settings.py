"""设置路由(管理员)。业务可调配置 DB 化 + 只读系统信息脱敏展示。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_superuser
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.services import runtime_config as rc

router = APIRouter(prefix="/api/settings", tags=["settings"])

# 可调配置的元信息:类型 + 校验。前端据此渲染对应控件。
# type: int / str / list_str
FIELD_DEFS = [
    # (key, label, type, group)
    ("UPLOAD_MAX_SIZE_MB", "单文件大小上限(MB)", "int", "upload"),
    ("UPLOAD_ALLOWED_EXTENSIONS", "允许的扩展名", "list_str", "upload"),
    ("ZIP_BOMB_RATIO", "ZIP 解压比上限", "int", "upload"),
    ("MINERU_API_URL", "MinerU 服务地址", "str", "ai"),
    ("EMBEDDING_SERVICE_URL", "Embedding 服务地址", "str", "ai"),
    ("DEFAULT_EMBEDDING_MODEL", "默认 Embedding 模型", "str", "ai"),
    ("VISION_IMAGE_MAX_LONG_EDGE", "视觉分析图片长边上限(px)", "int", "ai"),
    ("ACCESS_TOKEN_EXPIRE_MINUTES", "Token 有效期(分钟)", "int", "access"),
    ("CORS_ORIGINS", "CORS 允许的来源", "list_str", "access"),
]

# 分区标签
GROUP_LABELS = {
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
    }
    return getters[key]()


def _validate_value(key: str, ftype: str, value):
    """类型转换 + 基本合法性校验。返回转换后的值,或抛 HTTPException(400)。"""
    try:
        if ftype == "int":
            v = int(value)
            if v <= 0:
                raise ValueError("必须为正整数")
            return v
        if ftype == "str":
            v = str(value).strip()
            if not v:
                raise ValueError("不能为空")
            return v
        if ftype == "list_str":
            if isinstance(value, str):
                # 逗号分隔
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
    for key, label, ftype, group in FIELD_DEFS:
        groups.setdefault(group, []).append({
            "key": key,
            "label": label,
            "type": ftype,
            "value": _current_value(key),
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
    defs = {k: (label, ftype, group) for k, label, ftype, group in FIELD_DEFS}
    updated = []
    for key, value in body.items():
        if key not in defs:
            raise HTTPException(status_code=400, detail=f"未知配置项:{key}")
        _, ftype, _ = defs[key]
        converted = _validate_value(key, ftype, value)
        rc.set_setting(key, converted)
        updated.append(key)
    return {"detail": f"已更新 {len(updated)} 项", "updated": updated}


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
