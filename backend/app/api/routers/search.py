"""搜索路由(§8, ADR-0004 应用层 jieba, ADR-0003 阶段一仅全文路)。"""
from sqlalchemy import distinct, func, or_, select, text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.storage import get_storage
from app.db.session import get_db
from app.models import Presentation, PresentationVersion, Slide, User
from app.schemas.presentation import SlideOut
from app.services.tokenizer import query_segment

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/slides", response_model=list[SlideOut])
def search_slides(
    q: str = Query("", description="关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlideOut]:
    """关键词全文搜索(应用层 jieba 切词, simple tsvector)。默认仅当前版本。"""
    query = q.strip()
    storage = get_storage()

    # Base: slides of current versions, not deleted
    base = (
        db.query(Slide, Presentation.title.label("pres_title"))
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(Presentation.current_version_id == PresentationVersion.id)
    )

    if not query:
        # Empty query: return recent slides
        rows = (
            base.order_by(Slide.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    else:
        seg = query_segment(query)
        # Build tsquery against the segmented text_search column
        # Rank by ts_rank over the segmented text
        tsq = func.plainto_tsquery("simple", seg)
        rank = func.ts_rank(func.to_tsvector("simple", Slide.text_search), tsq)
        rows = (
            base.filter(Slide.text_search.isnot(None))
            .filter(func.to_tsvector("simple", Slide.text_search).op("@@")(tsq))
            .order_by(rank.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    out = []
    for s, pres_title in rows:
        prev = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append(SlideOut.from_model(s, preview_url=prev, thumbnail_url=thumb, presentation_title=pres_title))
    return out
