"""收藏查询辅助:避免 N+1,批量返回用户已收藏的 slide_id 集合。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Favorite


def favorite_slide_ids(db: Session, user_id: str, slide_ids: list[str]) -> set[str]:
    """返回当前用户在 slide_ids 中已收藏的 slide_id 集合(空输入返回空集)。"""
    if not slide_ids:
        return set()
    rows = (
        db.query(Favorite.slide_id)
        .filter(Favorite.user_id == user_id, Favorite.slide_id.in_(slide_ids))
        .all()
    )
    return {r[0] for r in rows}


def is_favorite(db: Session, user_id: str, slide_id: str) -> bool:
    """查询单页是否已被当前用户收藏。"""
    return (
        db.query(Favorite)
        .filter(Favorite.user_id == user_id, Favorite.slide_id == slide_id)
        .first()
        is not None
    )
