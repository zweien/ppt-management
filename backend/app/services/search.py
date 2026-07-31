"""build_search_index 服务(§8.1):为 slide 生成 text_search(simple tsvector)。

应用层 jieba 切词后写入 text_search 列(ADR-0004)。
索引字段(SE-01):标题 + 正文(native_text)+ 备注 + 表格文字 + 文件名
+ AI 摘要(ai_summary)+ AI 标签文本(SE-02:让 AI 语义参与检索)。

时序注意:全文索引在解析时建(ai_summary 尚无),AI 分析完成后需重索引
(见 tasks/ai.py analyze_visual 末尾补一次 index_slide),让 ai_summary 进入
全文索引与向量。
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Slide, SlideTag, Tag
from app.services.tokenizer import segment


def _extract_table_text(content_json: Any) -> str:
    """从 content_json.tables 提取表格文字(SE-01 表格检索)。"""
    if not content_json:
        return ""
    tables = content_json.get("tables") if isinstance(content_json, dict) else None
    if not tables or not isinstance(tables, list):
        return ""
    cells = []
    for tbl in tables:
        if not isinstance(tbl, dict):
            continue
        for row in tbl.get("rows", []):
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, str) and cell.strip():
                        cells.append(cell.strip())
    return " ".join(cells)


def get_ai_tag_names(db: Session, slide_id: str) -> list[str]:
    """取 slide 的 AI 标签文本(SlideTag origin='ai' → Tag.name)(SE-02)。

    用于入索引:让 AI 标签关键词可被全文/向量检索命中。
    """
    rows = (
        db.query(Tag.name)
        .join(SlideTag, SlideTag.tag_id == Tag.id)
        .filter(SlideTag.slide_id == slide_id, SlideTag.origin == "ai")
        .all()
    )
    return [r[0] for r in rows if r and r[0]]


def build_text_search(
    slide: Slide,
    presentation_title: str | None = None,
    ai_tag_names: list[str] | None = None,
) -> str:
    """组合用于全文检索与向量 embedding 的文本(SE-01/SE-02)。

    构成:标题 + 正文 + 备注 + 表格文字 + AI 摘要 + AI 标签 + 文件名。
    ai_summary 是 AI 生成的页面语义摘要,是语义检索的关键内容。
    ai_tag_names 传入该 slide 的 AI 标签文本(解析时为空,AI 分析后重索引时传入)。
    """
    parts = [
        slide.title or "",
        slide.native_text or "",
        slide.notes_text or "",
        _extract_table_text(slide.content_json),
        slide.ai_summary or "",  # SE-02:AI 摘要入索引(语义检索的关键)
    ]
    if ai_tag_names:
        parts.append(" ".join(ai_tag_names))  # SE-02:AI 标签文本
    if presentation_title:
        parts.append(presentation_title)
    combined = "\n".join(p for p in parts if p)
    return segment(combined)


def index_slide(db: Session, slide: Slide, presentation_title: str | None = None) -> None:
    """重建 slide 的全文索引。

    自动取该 slide 的 AI 标签文本(origin='ai');解析时无 AI 标签则为空。
    AI 分析完成后再次调用,让 ai_summary + AI 标签进入全文索引。
    """
    ai_tag_names = get_ai_tag_names(db, slide.id)
    seg = build_text_search(slide, presentation_title, ai_tag_names)
    slide.text_search = seg
    db.add(slide)
    db.commit()
