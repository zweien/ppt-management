"""API key 管理(SE-06):创建/列表/撤销。任何登录用户可管理自己的 key。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import ApiKey, User
from app.services.api_keys import generate_api_key, revoke_api_key

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


class ApiKeyCreateIn(BaseModel):
    name: str


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreatedOut(ApiKeyOut):
    full_key: str  # 仅创建时返回一次


def _to_out(k: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=k.id, name=k.name, key_prefix=k.key_prefix,
        created_at=k.created_at, last_used_at=k.last_used_at, revoked_at=k.revoked_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(ApiKey).filter(ApiKey.revoked_at.is_(None))
    if not user.is_superuser:
        q = q.filter(ApiKey.owner_id == user.id)
    return [_to_out(k) for k in q.order_by(ApiKey.created_at.desc()).all()]


@router.post("", response_model=ApiKeyCreatedOut, status_code=201)
def create_key(body: ApiKeyCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name 不能为空")
    rec, full_key = generate_api_key(db, user, name)
    out = _to_out(rec)
    return ApiKeyCreatedOut(**out.model_dump(), full_key=full_key)


@router.delete("/{key_id}", status_code=204)
def delete_key(key_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not revoke_api_key(db, key_id, user):
        raise HTTPException(status_code=404, detail="key 不存在或无权限")
