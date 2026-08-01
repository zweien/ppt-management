"""API key 服务(SE-06):生成/校验/撤销。只存 sha256 hash,完整 key 仅创建时返回一次。"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ApiKey, User

KEY_PREFIX = "pptk_"


def generate_api_key(db: Session, owner: User, name: str) -> tuple[ApiKey, str]:
    """生成新 API key。返回 (记录, 完整 key)。完整 key 只此一次可见。"""
    raw = secrets.token_urlsafe(32)
    full_key = f"{KEY_PREFIX}{raw}"
    rec = ApiKey(
        name=name,
        key_hash=hashlib.sha256(full_key.encode()).hexdigest(),
        key_prefix=full_key[: len(KEY_PREFIX) + 4],
        owner_id=owner.id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec, full_key


def verify_api_key(db: Session, key: str) -> User | None:
    """校验 X-API-Key,返回 owner 用户;无效/已撤销返回 None。"""
    if not key or not key.startswith(KEY_PREFIX):
        return None
    h = hashlib.sha256(key.encode()).hexdigest()
    rec = db.query(ApiKey).filter(ApiKey.key_hash == h, ApiKey.revoked_at.is_(None)).first()
    if not rec:
        return None
    rec.last_used_at = datetime.now(timezone.utc)
    db.add(rec)
    db.commit()
    return db.get(User, rec.owner_id)


def revoke_api_key(db: Session, key_id: str, owner: User) -> bool:
    """撤销 key(owner 本人或超管)。"""
    rec = db.get(ApiKey, key_id)
    if not rec:
        return False
    if rec.owner_id != owner.id and not owner.is_superuser:
        return False
    rec.revoked_at = datetime.now(timezone.utc)
    db.add(rec)
    db.commit()
    return True
