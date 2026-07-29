"""标签路由(SL-02~04)与收藏路由。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Favorite, Slide, SlideTag, Tag, User
from app.schemas.presentation import SlideTagOut, TagOut

router = APIRouter(prefix="/api", tags=["tags"])


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TagOut]:
    tags = db.query(Tag).filter(Tag.status == "active").order_by(Tag.name).all()
    return [TagOut(id=t.id, name=t.name, category=t.category, source=t.source, status=t.status) for t in tags]


class TagCreate(BaseModel):
    name: str
    category: str | None = None


@router.post("/tags", response_model=TagOut)
def create_tag(body: TagCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TagOut:
    existing = db.query(Tag).filter(Tag.name == body.name).first()
    if existing:
        return TagOut(id=existing.id, name=existing.name, category=existing.category, source=existing.source, status=existing.status)
    tag = Tag(name=body.name, category=body.category, source="manual", status="active")
    db.add(tag); db.commit(); db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, category=tag.category, source=tag.source, status=tag.status)


@router.patch("/tags/{tag_id}")
def update_tag(tag_id: str, body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    tag = db.get(Tag, tag_id)
    if not tag: raise HTTPException(404, "标签不存在")
    for k in ("name", "category", "status"):
        if k in body: setattr(tag, k, body[k])
    db.commit()
    return {"detail": "已更新"}


class BatchTagBody(BaseModel):
    slide_ids: list[str]
    tag_id: str


@router.post("/slides/batch-tags")
def batch_add_tags(body: BatchTagBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    for sid in body.slide_ids:
        existing = db.query(SlideTag).filter(SlideTag.slide_id == sid, SlideTag.tag_id == body.tag_id).first()
        if not existing:
            db.add(SlideTag(slide_id=sid, tag_id=body.tag_id, origin="manual", is_confirmed=True))
    db.commit()
    return {"detail": f"已为 {len(body.slide_ids)} 个页面添加标签"}


@router.delete("/slides/{slide_id}/tags/{tag_id}")
def remove_slide_tag(slide_id: str, tag_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    db.query(SlideTag).filter(SlideTag.slide_id == slide_id, SlideTag.tag_id == tag_id).delete()
    db.commit()
    return {"detail": "已移除标签"}


@router.get("/slides/{slide_id}/tags", response_model=list[SlideTagOut])
def slide_tags(slide_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[SlideTagOut]:
    rows = db.query(SlideTag, Tag).join(Tag, SlideTag.tag_id == Tag.id).filter(SlideTag.slide_id == slide_id).all()
    return [SlideTagOut(id=st.id, tag=TagOut(id=t.id, name=t.name, category=t.category, source=t.source, status=t.status),
                        origin=st.origin, confidence=st.confidence, is_confirmed=st.is_confirmed) for st, t in rows]


# --- Favorites ---

@router.get("/favorites")
def list_favorites(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    from app.core.storage import get_storage
    storage = get_storage()
    rows = (
        db.query(Slide, Favorite)
        .join(Favorite, Favorite.slide_id == Slide.id)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    out = []
    for s, _ in rows:
        thumb = storage.presigned_get_url(s.thumbnail_object_key) if s.thumbnail_object_key else None
        out.append({
            "id": s.id, "page_no": s.page_no, "title": s.title,
            "thumbnail_url": thumb, "parse_status": s.parse_status,
        })
    return out


class FavBody(BaseModel):
    slide_ids: list[str]


@router.post("/favorites")
def add_favorites(body: FavBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    for sid in body.slide_ids:
        if not db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.slide_id == sid).first():
            db.add(Favorite(user_id=user.id, slide_id=sid))
    db.commit()
    return {"detail": f"已收藏 {len(body.slide_ids)} 个页面"}


@router.delete("/favorites/{slide_id}")
def remove_favorite(slide_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.slide_id == slide_id).delete()
    db.commit()
    return {"detail": "已取消收藏"}
