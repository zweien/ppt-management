"""build_search_index 服务(§8.1):为 slide 生成 text_search(simple tsvector)。

应用层 jieba 切词后写入 text_search 列(ADR-0004)。
索引字段(SE-01):标题 + 正文(native_text)+ 备注 + 表格文字 + 文件名。
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Slide
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


def build_text_search(slide: Slide, presentation_title: str | None = None) -> str:
    """组合用于全文检索的文本:标题 + 正文 + 备注 + 表格文字 + 文件名(SE-01)。"""
    parts = [
        slide.title or "",
        slide.native_text or "",
        slide.notes_text or "",
        _extract_table_text(slide.content_json),
    ]
    if presentation_title:
        parts.append(presentation_title)
    combined = "\n".join(p for p in parts if p)
    return segment(combined)


def index_slide(db: Session, slide: Slide, presentation_title: str | None = None) -> None:
    seg = build_text_search(slide, presentation_title)
    slide.text_search = seg
    db.add(slide)
    db.commit()
