"""模型配置 schemas(§7.4, ADR-0006/0007)。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    capability: str = Field(..., pattern="^(text|vision|embedding)$")
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None  # 明文入参,服务端加密;返回时脱敏
    parameters: Optional[dict[str, Any]] = None
    allow_send_raw_image: bool = True
    allow_send_raw_text: bool = True
    is_enabled: bool = True
    is_default: bool = False


class ModelConfigCreate(ModelConfigBase):
    pass


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None  # 为空表示不改
    parameters: Optional[dict[str, Any]] = None
    allow_send_raw_image: Optional[bool] = None
    allow_send_raw_text: Optional[bool] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class ModelConfigOut(BaseModel):
    id: str
    name: str
    capability: str
    base_url: Optional[str]
    model: Optional[str]
    api_key_masked: Optional[str] = None  # 脱敏显示(清单16)
    parameters: Optional[dict[str, Any]] = None
    allow_send_raw_image: bool
    allow_send_raw_text: bool
    is_enabled: bool
    is_default: bool
    created_at: datetime

    @classmethod
    def from_model(cls, m) -> "ModelConfigOut":
        from app.core.crypto import mask_secret
        return cls(
            id=m.id, name=m.name, capability=m.capability,
            base_url=m.base_url, model=m.model,
            api_key_masked=mask_secret(m.api_key_ciphertext) if m.api_key_ciphertext else None,
            parameters=m.parameters, allow_send_raw_image=m.allow_send_raw_image,
            allow_send_raw_text=m.allow_send_raw_text, is_enabled=m.is_enabled,
            is_default=m.is_default, created_at=m.created_at,
        )


class ModelConfigTestResult(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    model_returned: Optional[str] = None
    error: Optional[str] = None
    sample: Optional[Any] = None
