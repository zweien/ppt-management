"""模型配置路由(§7.4, ADR-0006/0007)。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.crypto import encrypt_secret
from app.db.session import get_db
from app.models import ModelConfig, User
from app.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigTestResult,
    ModelConfigUpdate,
)
from app.services.model_provider import test_connection

router = APIRouter(prefix="/api/model-configs", tags=["model-configs"])


def _get(db: Session, cid: str) -> ModelConfig:
    m = db.get(ModelConfig, cid)
    if not m:
        raise HTTPException(404, "模型配置不存在")
    return m


@router.get("", response_model=list[ModelConfigOut])
def list_configs(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ModelConfigOut]:
    items = db.query(ModelConfig).order_by(ModelConfig.created_at.desc()).all()
    return [ModelConfigOut.from_model(m) for m in items]


@router.post("", response_model=ModelConfigOut)
def create_config(body: ModelConfigCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ModelConfigOut:
    m = ModelConfig(
        name=body.name, capability=body.capability, base_url=body.base_url,
        model=body.model, parameters=body.parameters,
        allow_send_raw_image=body.allow_send_raw_image,
        allow_send_raw_text=body.allow_send_raw_text,
        is_enabled=body.is_enabled, is_default=False,
    )
    if body.api_key:
        m.api_key_ciphertext = encrypt_secret(body.api_key)
    db.add(m)
    db.commit()
    if body.is_default:
        _set_default(db, m)
        db.commit()
    db.refresh(m)
    return ModelConfigOut.from_model(m)


@router.patch("/{cid}", response_model=ModelConfigOut)
def update_config(cid: str, body: ModelConfigUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> ModelConfigOut:
    m = _get(db, cid)
    for k in ("name", "base_url", "model", "parameters", "allow_send_raw_image",
              "allow_send_raw_text", "is_enabled"):
        v = getattr(body, k)
        if v is not None:
            setattr(m, k, v)
    if body.api_key:  # empty means don't change
        m.api_key_ciphertext = encrypt_secret(body.api_key)
    db.commit()
    if body.is_default:
        _set_default(db, m)
        db.commit()
    db.refresh(m)
    return ModelConfigOut.from_model(m)


@router.delete("/{cid}")
def delete_config(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    m = _get(db, cid)
    if m.is_default:
        raise HTTPException(400, "不能删除默认配置,请先切换默认")
    db.delete(m)
    db.commit()
    return {"detail": "已删除"}


@router.post("/{cid}/set-default", response_model=ModelConfigOut)
def set_default(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ModelConfigOut:
    m = _get(db, cid)
    _set_default(db, m)
    db.commit()
    db.refresh(m)
    return ModelConfigOut.from_model(m)


@router.post("/{cid}/test", response_model=ModelConfigTestResult)
def test_config(cid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ModelConfigTestResult:
    m = _get(db, cid)
    result = test_connection(m)
    return ModelConfigTestResult(
        success=result.success, latency_ms=result.latency_ms,
        model_returned=result.model_returned, error=result.error,
        sample=(result.content or (str(result.embedding[:3]) if result.embedding else None)),
    )


def _set_default(db: Session, m: ModelConfig) -> None:
    """设为同 capability 的默认(同 capability 仅一个 default)。"""
    db.query(ModelConfig).filter(
        ModelConfig.capability == m.capability, ModelConfig.is_default.is_(True)
    ).update({ModelConfig.is_default: False}, synchronize_session=False)
    m.is_default = True


@router.get("/defaults")
def get_defaults(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """返回各 capability 的默认配置 id(供 worker 查询)。"""
    rows = db.query(ModelConfig).filter(ModelConfig.is_default.is_(True)).all()
    return {r.capability: r.id for r in rows}
