"""重复页面治理 API(SE-05):重复组列表 + 单页相似查询。

- GET  /api/duplicates           全库重复组(exact 完全重复 / similar 高度相似)
- GET  /api/slides/{id}/similar  某页的高度相似页面(详情页提示)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import can_access, get_current_user
from app.core.storage import get_storage
from app.db import get_db
from app.models import Slide, User
from app.services.dedup import find_duplicate_groups, find_similar_slides

router = APIRouter(prefix="/api", tags=["duplicates"])


class DupSlideOut(BaseModel):
    slide_id: str
    page_no: int
    title: str | None
    presentation_id: str
    presentation_title: str | None
    thumbnail_url: str | None
    distance: int | None  # phash 汉明距离(exact 组为 None;similar 组内与代表的距离)


class DupGroupOut(BaseModel):
    kind: str  # exact / similar
    slides: list[DupSlideOut]


def _thumbs_for(db: Session, slide_ids: list[str]) -> dict[str, str | None]:
    """批量取缩略图 URL(presigned)。"""
    storage = get_storage()
    out: dict[str, str | None] = {}
    if not slide_ids:
        return out
    for s in db.query(Slide).filter(Slide.id.in_(slide_ids)).all():
        out[s.id] = (
            storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        )
    return out


@router.get("/duplicates", response_model=list[DupGroupOut])
def list_duplicates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DupGroupOut]:
    """全库重复组扫描(实时计算;库大后可加缓存/后台任务)。"""
    groups = find_duplicate_groups(db, user_id=user.id, superuser=user.is_superuser)
    all_ids = [m.slide_id for g in groups for m in g.slides]
    thumbs = _thumbs_for(db, all_ids)
    return [
        DupGroupOut(
            kind=g.kind,
            slides=[
                DupSlideOut(
                    slide_id=m.slide_id,
                    page_no=m.page_no,
                    title=m.title,
                    presentation_id=m.presentation_id,
                    presentation_title=m.presentation_title,
                    thumbnail_url=thumbs.get(m.slide_id),
                    distance=m.distance,
                )
                for m in g.slides
            ],
        )
        for g in groups
    ]


@router.get("/slides/{slide_id}/similar", response_model=list[DupSlideOut])
def get_similar_slides(
    slide_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DupSlideOut]:
    """某页的高度相似页面(fingerprint 相同 → 距离 0;phash ≤ 阈值)。"""
    slide = db.get(Slide, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="slide not found")
    # 权限:非超管只能看自己可见的 slide 的相似页(相似结果本身已按可见性过滤)
    from app.models import Presentation, PresentationVersion
    pres = (
        db.query(Presentation)
        .join(PresentationVersion, PresentationVersion.presentation_id == Presentation.id)
        .filter(PresentationVersion.id == slide.version_id)
        .first()
    )
    if pres and not can_access(user, pres):
        raise HTTPException(status_code=403, detail="forbidden")
    sims = find_similar_slides(db, slide_id, user_id=user.id, superuser=user.is_superuser)
    thumbs = _thumbs_for(db, [m.slide_id for m in sims])
    return [
        DupSlideOut(
            slide_id=m.slide_id,
            page_no=m.page_no,
            title=m.title,
            presentation_id=m.presentation_id,
            presentation_title=m.presentation_title,
            thumbnail_url=thumbs.get(m.slide_id),
            distance=m.distance,
        )
        for m in sims
    ]
