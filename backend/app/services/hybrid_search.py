"""混合检索融合(ADR-0003/0007):RRF + 结构化加分。

- 全文路:ts_rank_cd over simple tsvector,top-N
- 向量路:pgvector cosine,<=> top-N(若有 default embedding 配置且有向量)
- 融合:RRF(k=60)取每路 top-100,叠加 bonus(标题/文件名精确匹配、人工标签匹配、收藏加权)
- 命中原因:每条结果返回 hit_reasons
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, or_, text as _sa_text
from sqlalchemy.orm import Session

from app.models import Favorite, ModelConfig, Slide, SlideTag, Tag
from app.services.tokenizer import query_segment

logger = logging.getLogger(__name__)

RRF_K = 60  # ADR-0003
EACH_TOPN = 100
RRF_BASE = 1.0
BONUS_TITLE_EXACT = 3.0
BONUS_FILENAME_EXACT = 2.0
BONUS_MANUAL_TAG = 2.5
BONUS_AI_TAG = 1.0
BONUS_FAVORITE = 1.5


@dataclass
class HybridHit:
    slide: Slide
    score: float
    hit_reasons: list[str] = field(default_factory=list)
    text_rank: int | None = None
    vector_rank: int | None = None
    presentation_title: str | None = None


def _has_vector_search(db: Session) -> ModelConfig | None:
    return (
        db.query(ModelConfig)
        .filter(ModelConfig.capability == "embedding", ModelConfig.is_default.is_(True), ModelConfig.is_enabled.is_(True))
        .first()
    )


def _text_recall(db: Session, seg: str, topn: int, include_historical: bool = False, user_id: str | None = None, superuser: bool = False) -> list[tuple[Slide, str, int]]:
    """全文召回,返回 [(slide, pres_title, rank_index)]"""
    tsq = func.plainto_tsquery("simple", seg)
    from app.models import Presentation, PresentationVersion
    q = (
        db.query(Slide, Presentation.title, func.ts_rank(func.to_tsvector("simple", Slide.text_search), tsq).label("rank"))
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(func.to_tsvector("simple", Slide.text_search).op("@@")(tsq))
    )
    if not include_historical:
        q = q.filter(Presentation.current_version_id == PresentationVersion.id)
    # 可见性过滤:超管看全部;普通用户 = team 共享 + 自己的 private
    if not superuser and user_id:
        q = q.filter(or_(Presentation.visibility == "team", Presentation.owner_id == user_id))
    rows = q.order_by(_sa_text("rank desc")).limit(topn).all()
    return [(r[0], r[1], i + 1) for i, r in enumerate(rows)]


def _vector_recall(db: Session, seg: str, topn: int, include_historical: bool = False, user_id: str | None = None, superuser: bool = False) -> list[tuple[Slide, str, int]]:
    """向量召回(若有 default embedding 配置且有向量数据)"""
    if not _has_vector_search(db):
        return []
    from app.models import Presentation, PresentationVersion, SlideEmbedding
    # embed the query
    try:
        from app.tasks.ai import _get_default_config, build_embedding_task  # noqa: F401
    except Exception:
        pass
    from app.services.model_provider import ModelProvider
    config = _has_vector_search(db)
    r = ModelProvider(config, timeout=30.0).embed(seg)
    if not r.success or not r.embedding:
        return []
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in r.embedding) + "]"
    sql = _sa_text("""
        SELECT se.slide_id, e.distance
        FROM slide_embeddings se
        CROSS JOIN LATERAL (
            SELECT (se.embedding <=> CAST(:vec AS vector)) AS distance
        ) e
        WHERE se.status = 'success'
        ORDER BY se.embedding <=> CAST(:vec AS vector)
        LIMIT :lim
    """)
    rows = db.execute(sql, {"vec": vec_literal, "lim": topn}).fetchall()
    slide_ids = [str(rw[0]) for rw in rows]
    if not slide_ids:
        return []
    slides_q = (
        db.query(Slide, Presentation.title)
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(Slide.id.in_(slide_ids))
    )
    if not include_historical:
        slides_q = slides_q.filter(Presentation.current_version_id == PresentationVersion.id)
    # 可见性过滤
    if not superuser and user_id:
        slides_q = slides_q.filter(or_(Presentation.visibility == "team", Presentation.owner_id == user_id))
    slides_q = slides_q.all()
    by_id = {s.id: (s, t) for s, t in slides_q}
    out = []
    for i, rw in enumerate(rows):
        sid = str(rw[0])
        if sid in by_id:
            s, t = by_id[sid]
            out.append((s, t, i + 1))
    return out


def _apply_filters(base_slide_ids: set, db: Session, tag_ids: list[str]) -> set:
    """标签筛选:AND across dimensions, OR within. 简化版:命中任一标签即保留。"""
    if not tag_ids:
        return base_slide_ids
    rows = db.query(SlideTag.slide_id).filter(SlideTag.tag_id.in_(tag_ids)).distinct().all()
    allowed = {str(r[0]) for r in rows}
    return base_slide_ids & allowed


def hybrid_search(
    db: Session,
    query: str,
    *,
    tag_ids: list[str] | None = None,
    favorite_user_id: str | None = None,
    favorite_only: bool = False,
    include_historical: bool = False,
    topn: int = 24,
    user_id: str | None = None,
    superuser: bool = False,
) -> list[HybridHit]:
    """执行混合检索,返回排序后的 HybridHit 列表。"""
    seg = query_segment(query) if query else ""
    if not seg and not tag_ids and not favorite_only:
        # empty: return recent
        from app.models import Presentation, PresentationVersion
        q = (
            db.query(Slide, Presentation.title)
            .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
            .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
            .filter(Presentation.deleted_at.is_(None))
        )
        if not include_historical:
            q = q.filter(Presentation.current_version_id == PresentationVersion.id)
        if not superuser and user_id:
            q = q.filter(or_(Presentation.visibility == "team", Presentation.owner_id == user_id))
        rows = q.order_by(Slide.created_at.desc()).limit(topn).all()
        return [HybridHit(slide=s, score=0.0, presentation_title=t) for s, t in rows]

    # recall both paths
    text_hits = _text_recall(db, seg, EACH_TOPN, include_historical, user_id, superuser) if seg else []
    vec_hits = _vector_recall(db, seg, EACH_TOPN, include_historical, user_id, superuser) if seg else []

    # collect candidates
    candidates: dict[str, HybridHit] = {}
    for s, t, rank in text_hits:
        h = candidates.setdefault(s.id, HybridHit(slide=s, score=0.0, presentation_title=t))
        h.text_rank = rank
        h.score += RRF_BASE / (RRF_K + rank)
        h.hit_reasons.append("正文命中")
    for s, t, rank in vec_hits:
        h = candidates.setdefault(s.id, HybridHit(slide=s, score=0.0, presentation_title=t))
        h.vector_rank = rank
        h.score += RRF_BASE / (RRF_K + rank)
        h.hit_reasons.append("语义相似")

    # if pure filter (no query), start from all current slides
    if not seg:
        from app.models import Presentation, PresentationVersion
        q = (
            db.query(Slide, Presentation.title)
            .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
            .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
            .filter(Presentation.deleted_at.is_(None))
        )
        if not include_historical:
            q = q.filter(Presentation.current_version_id == PresentationVersion.id)
        if not superuser and user_id:
            q = q.filter(or_(Presentation.visibility == "team", Presentation.owner_id == user_id))
        rows = q.limit(EACH_TOPN).all()
        for s, t in rows:
            candidates.setdefault(s.id, HybridHit(slide=s, score=0.0, presentation_title=t))

    # structural bonuses
    q_lower = (query or "").lower().strip()
    for h in candidates.values():
        s = h.slide
        title = (s.title or "").lower()
        fname = (h.presentation_title or "").lower()
        if q_lower and title == q_lower:
            h.score += BONUS_TITLE_EXACT
            h.hit_reasons.append("标题精确")
        elif q_lower and title and q_lower in title:
            h.score += BONUS_TITLE_EXACT / 2
            h.hit_reasons.append("标题匹配")
        if q_lower and fname and q_lower in fname:
            h.score += BONUS_FILENAME_EXACT
            h.hit_reasons.append("文件名匹配")

    # tag bonuses
    if tag_ids:
        tag_rows = (
            db.query(SlideTag.slide_id, SlideTag.origin)
            .filter(SlideTag.tag_id.in_(tag_ids))
            .all()
        )
        tag_map: dict[str, set[str]] = {}
        for sid, origin in tag_rows:
            tag_map.setdefault(str(sid), set()).add(origin)
        for h in candidates.values():
            origins = tag_map.get(h.slide.id, set())
            if origins:
                if "manual" in origins:
                    h.score += BONUS_MANUAL_TAG
                    h.hit_reasons.append("人工标签")
                if "ai" in origins:
                    h.score += BONUS_AI_TAG
                    if "人工标签" not in h.hit_reasons:
                        h.hit_reasons.append("AI 标签")

    # favorite filter/bonus
    if favorite_only and favorite_user_id:
        fav_ids = {str(r[0]) for r in db.query(Favorite.slide_id).filter(Favorite.user_id == favorite_user_id).all()}
        candidates = {k: v for k, v in candidates.items() if k in fav_ids}
    elif favorite_user_id:
        fav_ids = {str(r[0]) for r in db.query(Favorite.slide_id).filter(Favorite.user_id == favorite_user_id).all()}
        for h in candidates.values():
            if h.slide.id in fav_ids:
                h.score += BONUS_FAVORITE
                h.hit_reasons.append("已收藏")

    # dedupe hit_reasons, keep order
    for h in candidates.values():
        seen = set()
        h.hit_reasons = [x for x in h.hit_reasons if not (x in seen or seen.add(x))]

    ranked = sorted(candidates.values(), key=lambda h: h.score, reverse=True)
    return ranked[:topn]
