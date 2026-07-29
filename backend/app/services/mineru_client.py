"""MinerU HTTP 客户端(ADR-0007 §6)。

通过宿主机 mineru-api 服务(POST /file_parse)解析 PPTX/PDF,产出 Markdown + 结构化 JSON。
MinerU 本体在宿主机 venv,worker 仅做 HTTP 编排。
"""
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MinerUResult:
    success: bool
    markdown: str = ""
    content_list: list = None
    raw: dict | None = None
    error: str | None = None


def _base_url() -> str:
    return (settings.MINERU_API_URL or "http://host.docker.internal:8765").rstrip("/")


def parse_pdf_sync(pdf_bytes: bytes, filename: str = "preview.pdf", lang: str = "ch", timeout: float = 600.0) -> MinerUResult:
    """同步调用 mineru-api /file_parse,上传 PDF 字节,返回 Markdown。

    backend=pipeline(Layout/OCR on GPU);hybrid-engine 在本机 GB10 上 device_map 失败。
    """
    url = f"{_base_url()}/file_parse"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                files={"files": (filename, pdf_bytes, "application/pdf")},
                data={"parse_method": "auto", "backend": "pipeline"},
            )
        if resp.status_code != 200:
            return MinerUResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        md = _extract_markdown(data)
        content = _extract_content_list(data)
        if not md and not content:
            return MinerUResult(success=False, error="empty result", raw=data)
        return MinerUResult(success=True, markdown=md, content_list=content, raw=data)
    except Exception as e:
        logger.warning("MinerU parse failed: %s", e)
        return MinerUResult(success=False, error=str(e)[:300])


def health() -> bool:
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{_base_url()}/health")
        return r.status_code == 200
    except Exception:
        return False


def _extract_markdown(data: dict) -> str:
    """mineru-api /file_parse 返回结构兼容多种形态。

    实测 3.4.4 pipeline 后端:results.<filename>.md_content
    """
    # 形态1: 顶层 md / markdown
    for key in ("md", "markdown", "md_content"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v
    # 形态2: results 是 dict {<filename>: {md_content: ...}}
    results = data.get("results")
    if isinstance(results, dict):
        for item in results.values():
            if isinstance(item, dict):
                for key in ("md_content", "md", "markdown"):
                    v = item.get(key)
                    if isinstance(v, str) and v.strip():
                        return v
    # 形态3: results 是 list
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                for key in ("md_content", "md", "markdown"):
                    v = item.get(key)
                    if isinstance(v, str) and v.strip():
                        return v
            elif isinstance(item, str) and item.strip():
                return item
    return ""


def _extract_content_list(data: dict) -> list:
    for key in ("content_list", "content_list_v2", "middle_json"):
        v = data.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict) and isinstance(v.get("content_list"), list):
            return v["content_list"]
    return []
