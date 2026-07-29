"""ModelProvider 统一适配层(ADR-0001 §16.2, ADR-0007 §1)。

业务代码不直接依赖厂商 SDK,统一走 OpenAI 兼容协议:
- 文本/视觉:POST /v1/chat/completions
- Embedding:POST /v1/embeddings
"""
import base64
import io
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.crypto import decrypt_secret
from app.models import ModelConfig


@dataclass
class ProviderResult:
    success: bool
    latency_ms: int = 0
    model_returned: str | None = None
    content: str | None = None  # chat content or error text
    embedding: list[float] | None = None
    raw: Any = None
    error: str | None = None


def _auth_headers(config: ModelConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key_ciphertext:
        try:
            key = decrypt_secret(config.api_key_ciphertext)
            headers["Authorization"] = f"Bearer {key}"
        except Exception:
            pass
    return headers


def _base(config: ModelConfig) -> str:
    return (config.base_url or "").rstrip("/")


class ModelProvider:
    """统一模型调用接口。"""

    def __init__(self, config: ModelConfig, timeout: float = 60.0) -> None:
        self.config = config
        self.timeout = timeout

    # --- Chat (text & vision) ---

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResult:
        payload: dict[str, Any] = {
            "model": self.config.model or "",
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        params = self.config.parameters or {}
        for k in ("top_p", "presence_penalty", "frequency_penalty"):
            if k in params:
                payload[k] = params[k]

        url = f"{_base(self.config)}/v1/chat/completions"
        return self._post_chat(url, payload)

    def chat_with_image(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        image_media: str = "image/png",
        *,
        json_mode: bool = True,
        max_tokens: int = 1024,
    ) -> ProviderResult:
        """Vision: send image as base64 data URL."""
        if not self.config.allow_send_raw_image:
            return ProviderResult(success=False, error="config disabled raw image sending")
        b64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:{image_media};base64,{b64}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        return self.chat(messages, json_mode=json_mode, max_tokens=max_tokens)

    def _post_chat(self, url: str, payload: dict) -> ProviderResult:
        t0 = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=_auth_headers(self.config))
            latency = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                return ProviderResult(success=False, latency_ms=latency,
                                      error=f"HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            content = ""
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content") or ""
            return ProviderResult(success=True, latency_ms=latency,
                                  model_returned=data.get("model"), content=content, raw=data)
        except Exception as e:
            return ProviderResult(success=False, latency_ms=int((time.time() - t0) * 1000),
                                  error=str(e)[:300])

    # --- Embedding ---

    def embed(self, texts: list[str] | str) -> ProviderResult:
        if not self.config.allow_send_raw_text:
            return ProviderResult(success=False, error="config disabled raw text sending")
        if isinstance(texts, str):
            texts = [texts]
        params = self.config.parameters or {}
        payload: dict[str, Any] = {
            "model": self.config.model or "",
            "input": texts,
        }
        for k in ("dimensions", "encoding_format"):
            if k in params:
                payload[k] = params[k]
        url = f"{_base(self.config)}/v1/embeddings"
        t0 = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=_auth_headers(self.config))
            latency = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                return ProviderResult(success=False, latency_ms=latency,
                                      error=f"HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            datas = [item.get("embedding") for item in data.get("data", [])]
            emb = datas[0] if datas else None
            return ProviderResult(success=True, latency_ms=latency,
                                  model_returned=data.get("model"), embedding=emb, raw=data)
        except Exception as e:
            return ProviderResult(success=False, latency_ms=int((time.time() - t0) * 1000),
                                  error=str(e)[:300])


# --- Connection test (MC-04) ---

def test_connection(config: ModelConfig) -> ProviderResult:
    """能力测试:发一个最小请求,返回耗时/模型名/错误。"""
    provider = ModelProvider(config, timeout=30.0)
    if config.capability == "embedding":
        return provider.embed("test")
    if config.capability == "vision":
        # vision test: a tiny 1x1 png, ask for trivial json
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        return provider.chat_with_image(
            "你是测试助手。", "请返回 JSON {\"ok\":true}", tiny_png, max_tokens=32
        )
    # text
    return provider.chat([{"role": "user", "content": "ping"}], max_tokens=8)
