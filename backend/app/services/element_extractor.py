"""元素级提取(SE-04):从 slide content_json 提取文本框+图片,入 slide_elements。

解析时同步提取文本框(快);图片 OCR 作为异步任务(重,调 MinerU)。
文本框 text 直接入索引;图片先存引用(text 空),OCR 完成后更新 text + embedding。
"""
import logging

from sqlalchemy.orm import Session

from app.models import Slide, SlideElement
from app.services.search import index_slide
from app.services.tokenizer import segment

logger = logging.getLogger(__name__)


def extract_and_index_elements(db: Session, slide: Slide, presentation_title: str | None = None) -> int:
    """从 slide content_json 提取文本框+图片,入 slide_elements。

    返回提取的元素数。幂等:先删旧元素再插(re-parse 安全)。
    图片元素 text 为空(OCR 后由 ocr_element_task 更新)。
    """
    cj = slide.content_json or {}
    shapes = cj.get("shapes", []) or []
    pictures = cj.get("pictures", []) or []
    tables = cj.get("tables", []) or []

    # 幂等:先删旧元素
    db.query(SlideElement).filter(SlideElement.slide_id == slide.id).delete()

    idx = 0
    # 文本框
    for sh in shapes:
        text = (sh.get("text") or "").strip()
        if not text:
            continue
        el = SlideElement(
            slide_id=slide.id,
            element_index=idx,
            element_type=sh.get("type", "textbox"),
            text=text,
            text_search=segment(text),
            embedding_status="pending",
        )
        db.add(el)
        idx += 1

    # 表格(拼合文字)
    for tbl in tables:
        rows = tbl.get("rows", []) or []
        cells = []
        for row in rows:
            for cell in row:
                if isinstance(cell, str) and cell.strip():
                    cells.append(cell.strip())
        if not cells:
            continue
        text = " ".join(cells)
        el = SlideElement(
            slide_id=slide.id,
            element_index=idx,
            element_type="table",
            text=text,
            text_search=segment(text),
            embedding_status="pending",
        )
        db.add(el)
        idx += 1

    # 图片(先存引用,text 空,OCR 后更新)
    for pic in pictures:
        target = pic.get("target")
        if not target:
            continue
        el = SlideElement(
            slide_id=slide.id,
            element_index=idx,
            element_type="picture",
            text=None,  # OCR 后更新
            image_rId=pic.get("rId"),
            image_target=target,
            image_position=pic.get("position"),
            text_search=None,
            embedding_status="pending",
        )
        db.add(el)
        idx += 1

    db.commit()
    logger.info("extracted %d elements for slide %s", idx, slide.id)
    return idx
