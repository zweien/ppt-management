"""视觉模型结构化分析(ADR-0007 §2/§3, PRD §9.5)。

整页 PNG → 受约束 JSON(summary/topics/page_purpose/content_types/visual_styles/use_cases/key_entities/confidence)。
发送前缩放到长边 ≤1568px。失败重试 1 次。产出 AI 摘要 + AI 标签。
"""
import io
import json
import logging
from dataclasses import dataclass
from typing import Any

from PIL import Image  # Pillow

from app.core.config import settings
from app.models import ModelConfig
from app.services.model_provider import ModelProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 PPT 页面分析专家。仔细观察这页 PPT 的图片,输出严格的 JSON,字段如下:
{
  "summary": "本页内容的一句话摘要(中文)",
  "topics": ["主题1", "主题2"],
  "page_purpose": ["总体方案"|"项目申报"|"答辩汇报"|"总结报告"|"技术方案"|"背景介绍"|"其他"],
  "content_types": ["架构图"|"数据图表"|"图文混排"|"纯文字"|"表格"|"流程图"|"其他"],
  "visual_styles": ["科技风"|"商务风"|"学术风"|"紫色系"|"蓝色系"|"深色"|"浅色"|"极简"],
  "use_cases": ["项目申报"|"答辩汇报"|"技术评审"|"内部汇报"|"对外展示"],
  "key_entities": ["关键实体1", "关键实体2"],
  "confidence": 0.0到1.0的浮点数
}
只返回 JSON,不要任何解释或 markdown 代码块标记。page_purpose/content_types/visual_styles/use_cases 尽量使用上述推荐值,也可适当补充。"""

REQUIRED_FIELDS = {"summary", "topics", "page_purpose", "content_types", "visual_styles", "use_cases"}


@dataclass
class VisionResult:
    success: bool
    analysis: dict[str, Any] | None = None
    latency_ms: int = 0
    model_returned: str | None = None
    error: str | None = None


def _scale_image(image_bytes: bytes, max_long_edge: int) -> bytes:
    """等比缩放 PNG,长边 ≤ max_long_edge(ADR-0007 §2)。"""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _parse_json_content(content: str) -> dict[str, Any] | None:
    """容错解析模型返回的 JSON(可能裹了 markdown 代码块)。"""
    if not content:
        return None
    text = content.strip()
    # strip ```json ... ``` fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # try to extract first {...} block
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    return obj


def _validate(obj: dict[str, Any]) -> dict[str, Any] | None:
    """Schema 校验:必填字段存在,列表字段归一为 list。"""
    if not REQUIRED_FIELDS.issubset(obj.keys()):
        return None
    for k in ("topics", "page_purpose", "content_types", "visual_styles", "use_cases", "key_entities"):
        v = obj.get(k)
        if v is None:
            obj[k] = []
        elif isinstance(v, str):
            obj[k] = [v]
        elif not isinstance(v, list):
            obj[k] = []
    if "confidence" in obj:
        try:
            obj["confidence"] = float(obj["confidence"])
        except (TypeError, ValueError):
            obj["confidence"] = 0.5
    return obj


def analyze_slide_image(config: ModelConfig, image_bytes: bytes) -> VisionResult:
    """对单页 PNG 做视觉分析,返回结构化 JSON。失败重试 1 次。"""
    provider = ModelProvider(config, timeout=90.0)
    from app.services.runtime_config import get_vision_max_long_edge
    scaled = _scale_image(image_bytes, get_vision_max_long_edge())

    for attempt in range(2):
        r = provider.chat_with_image(
            system_prompt=SYSTEM_PROMPT,
            user_text="请分析这页 PPT 并返回 JSON。",
            image_bytes=scaled,
            json_mode=True,
            max_tokens=900,
        )
        if not r.success:
            if attempt == 0:
                continue
            return VisionResult(success=False, error=r.error, latency_ms=r.latency_ms)
        obj = _parse_json_content(r.content or "")
        if obj is None:
            if attempt == 0:
                logger.warning("vision JSON parse failed, retrying: %s", (r.content or "")[:120])
                continue
            return VisionResult(success=False, error="JSON parse failed", latency_ms=r.latency_ms,
                                 model_returned=r.model_returned)
        validated = _validate(obj)
        if validated is None:
            if attempt == 0:
                logger.warning("vision schema validation failed, retrying: %s", list(obj.keys()))
                continue
            return VisionResult(success=False, error="schema validation failed", latency_ms=r.latency_ms,
                                 model_returned=r.model_returned)
        return VisionResult(success=True, analysis=validated, latency_ms=r.latency_ms,
                            model_returned=r.model_returned)

    return VisionResult(success=False, error="exhausted retries")
