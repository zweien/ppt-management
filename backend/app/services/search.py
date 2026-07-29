"""build_search_index 服务(§8.1):为 slide 生成 text_search(simple tsvector)。

应用层 jieba 切词后写入 text_search 列(ADR-0004)。
"""
from sqlalchemy.orm import Session

from app.models import Slide
from app.services.tokenizer import segment


def build_text_search(slide: Slide) -> str:
    """Compose segmented text from title + native_text + notes_text (+ filename via caller)."""
    parts = [slide.title or "", slide.native_text or "", slide.notes_text or ""]
    combined = "\n".join(p for p in parts if p)
    return segment(combined)


def index_slide(db: Session, slide: Slide) -> None:
    seg = build_text_search(slide)
    slide.text_search = seg
    db.add(slide)
    db.commit()
