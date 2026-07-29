"""搜索路由(§8, ADR-0003/0004/0007):RRF 混合检索 + 标签筛选 + 命中原因 + 文件聚合。"""
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.storage import get_storage
from app.db.session import get_db
from app.models import Presentation, PresentationVersion, Slide, Tag, User
from app.schemas.presentation import SlideOut
from app.services.hybrid_search import hybrid_search

router = APIRouter(prefix="/api/search", tags=["search"])


class HitReasonOut(BaseModel):
    slide: SlideOut
    score: float
    hit_reasons: list[str]


@router.get("/slides", response_model=list[HitReasonOut])
def search_slides(
    q: str = Query("", description="关键词"),
    tag_ids: str = Query("", description="逗号分隔的标签 id"),
    favorite_only: bool = Query(False),
    include_historical: bool = Query(False, description="包含历史版本(非当前版本)"),
    sort: str = Query("relevance", pattern="^(relevance|recent|title)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HitReasonOut]:
    """混合检索(RRF + bonus)。返回命中原因。"""
    storage = get_storage()
    tids = [t.strip() for t in tag_ids.split(",") if t.strip()] if tag_ids else []

    query = q.strip()
    hits = hybrid_search(
        db, query, tag_ids=tids,
        favorite_user_id=user.id, favorite_only=favorite_only,
        include_historical=include_historical,
        topn=page * page_size,
    )

    # sort override
    if sort == "recent":
        hits.sort(key=lambda h: h.slide.created_at, reverse=True)
    elif sort == "title":
        hits.sort(key=lambda h: (h.slide.title or ""))

    # paginate
    start = (page - 1) * page_size
    page_hits = hits[start:start + page_size]

    out = []
    for h in page_hits:
        s = h.slide
        prev = storage.presigned_get_url(s.preview_object_key) if s.preview_object_key else None
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        slide_out = SlideOut.from_model(s, preview_url=prev, thumbnail_url=thumb,
                                        presentation_title=h.presentation_title)
        out.append(HitReasonOut(slide=slide_out, score=round(h.score, 4),
                                hit_reasons=h.hit_reasons))
    return out


@router.get("/presentations", response_model=list[dict])
def search_presentations(
    q: str = Query(""),
    tag_ids: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """文件聚合视图:按文件分组展示命中页面(SE-04)。"""
    storage = get_storage()
    tids = [t.strip() for t in tag_ids.split(",") if t.strip()] if tag_ids else []
    hits = hybrid_search(db, q.strip(), tag_ids=tids, topn=page * page_size * 2)

    # group by presentation
    groups: dict[str, dict] = {}
    order = []
    for h in hits:
        s = h.slide
        pres_id = None
        version = db.get(PresentationVersion, s.version_id)
        if version:
            pres_id = version.presentation_id
        key = pres_id or "unknown"
        if key not in groups:
            pres = db.get(Presentation, key) if pres_id else None
            groups[key] = {"id": key, "title": pres.title if pres else h.presentation_title or "",
                           "slides": []}
            order.append(key)
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        groups[key]["slides"].append({
            "id": s.id, "page_no": s.page_no, "title": s.title,
            "thumbnail_url": thumb, "hit_reasons": h.hit_reasons,
        })

    return [groups[k] for k in order][:page_size]


@router.get("/tag-facets")
def tag_facets(
    q: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """标签分面:返回各标签及其在当前结果集中的命中数(供筛选 UI)。"""
    from app.models import SlideTag
    hits = hybrid_search(db, q.strip(), topn=200)
    slide_ids = [h.slide.id for h in hits]
    if not slide_ids:
        return []
    rows = (
        db.query(Tag.id, Tag.name, Tag.category, func_count(SlideTag.slide_id))
        .join(SlideTag, SlideTag.tag_id == Tag.id)
        .filter(SlideTag.slide_id.in_(slide_ids))
        .group_by(Tag.id, Tag.name, Tag.category)
        .order_by(Tag.category, Tag.name)
        .all()
    )
    return [{"id": r[0], "name": r[1], "category": r[2], "count": r[3]} for r in rows]


# import here to avoid circular
from sqlalchemy import func as _f


def func_count(col):
    return _f.count(col)
