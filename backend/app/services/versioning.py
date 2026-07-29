"""版本识别与页面变化匹配(ADR-0008)。

版本识别:页面指纹集合 Jaccard 相似度(建议,非强制)。
页面匹配:指纹精确匹配 + pHash 视觉比对,判定增删改重排。
"""
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Presentation, PresentationVersion, Slide, VersionSlideMatch

logger = logging.getLogger(__name__)

VERSION_SUGGEST_THRESHOLD = 0.5  # Jaccard >= 阈值才建议
PHASH_MODIFIED_THRESHOLD = 8  # Hamming distance ≤ 阈值视为视觉接近(可能修改)


@dataclass
class VersionCandidate:
    presentation_id: str
    title: str
    similarity: float
    page_count: int


def _version_fingerprints(db: Session, version_id: str) -> set[str]:
    rows = db.query(Slide.fingerprint).filter(
        Slide.version_id == version_id, Slide.fingerprint.isnot(None)
    ).all()
    return {r[0] for r in rows if r[0]}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def suggest_version_candidates(
    db: Session, new_fingerprints: set[str], page_count: int, exclude_pres_id: str | None = None
) -> list[VersionCandidate]:
    """对一组新指纹,找出最可能成为其新版本的已有 presentation(按 Jaccard)。

    供上传时调用:先解析新文件的指纹,再与本库已有当前版本比对。
    """
    if not new_fingerprints:
        return []
    # 取所有未删除 presentation 的当前版本指纹
    rows = (
        db.query(Presentation.id, Presentation.title, Presentation.current_version_id)
        .filter(Presentation.deleted_at.is_(None))
        .all()
    )
    candidates: list[VersionCandidate] = []
    for pres_id, title, cur_vid in rows:
        if exclude_pres_id and pres_id == exclude_pres_id:
            continue
        if not cur_vid:
            continue
        existing_fps = _version_fingerprints(db, cur_vid)
        if not existing_fps:
            continue
        sim = _jaccard(new_fingerprints, existing_fps)
        if sim >= VERSION_SUGGEST_THRESHOLD:
            cnt = db.query(Slide).filter(Slide.version_id == cur_vid).count()
            candidates.append(VersionCandidate(pres_id, title, round(sim, 3), cnt))
    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates


# ============ 页面变化匹配 ============

def _hamming_phash(a: str | None, b: str | None) -> int | None:
    """两个 hex pHash 的 Hamming 距离。任一为空返回 None。"""
    if not a or not b:
        return None
    try:
        ia, ib = int(a, 16), int(b, 16)
    except ValueError:
        return None
    return bin(ia ^ ib).count("1")


def match_versions(db: Session, from_version_id: str, to_version_id: str) -> int:
    """计算两个版本间的页面匹配,写入 version_slide_matches。返回匹配条数。

    from = 旧版本,to = 新版本。
    """
    # 清理旧匹配(重算场景)
    db.query(VersionSlideMatch).filter(
        VersionSlideMatch.from_version_id == from_version_id,
        VersionSlideMatch.to_version_id == to_version_id,
    ).delete()

    old_slides = (
        db.query(Slide).filter(Slide.version_id == from_version_id).order_by(Slide.page_no).all()
    )
    new_slides = (
        db.query(Slide).filter(Slide.version_id == to_version_id).order_by(Slide.page_no).all()
    )

    old_by_fp: dict[str, Slide] = {}
    for s in old_slides:
        if s.fingerprint:
            old_by_fp.setdefault(s.fingerprint, s)
    new_by_fp: dict[str, Slide] = {}
    for s in new_slides:
        if s.fingerprint:
            new_by_fp.setdefault(s.fingerprint, s)

    matched_new: set[str] = set()
    matched_old: set[str] = set()
    rows: list[VersionSlideMatch] = []

    # 1) fingerprint 精确匹配 → unchanged / rearranged
    for new_fp, new_s in new_by_fp.items():
        old_s = old_by_fp.get(new_fp)
        if old_s:
            mtype = "rearranged" if old_s.page_no != new_s.page_no else "unchanged"
            rows.append(VersionSlideMatch(
                from_slide_id=old_s.id, to_slide_id=new_s.id,
                from_version_id=from_version_id, to_version_id=to_version_id,
                match_type=mtype, score=1.0,
            ))
            matched_new.add(new_s.id)
            matched_old.add(old_s.id)

    # 2) 剩余未匹配的:用 pHash 最近邻 → modified
    unmatched_new = [s for s in new_slides if s.id not in matched_new]
    unmatched_old = [s for s in old_slides if s.id not in matched_old]
    for new_s in unmatched_new:
        best_old = None
        best_dist = None
        for old_s in unmatched_old:
            d = _hamming_phash(new_s.visual_phash, old_s.visual_phash)
            if d is not None and (best_dist is None or d < best_dist):
                best_dist, best_old = d, old_s
        if best_old is not None and best_dist is not None and best_dist <= PHASH_MODIFIED_THRESHOLD:
            rows.append(VersionSlideMatch(
                from_slide_id=best_old.id, to_slide_id=new_s.id,
                from_version_id=from_version_id, to_version_id=to_version_id,
                match_type="modified", score=1 - best_dist / 64.0,
            ))
            matched_new.add(new_s.id)
            unmatched_old = [s for s in unmatched_old if s.id != best_old.id]

    # 3) 新版本中仍未匹配 → added
    for new_s in new_slides:
        if new_s.id not in matched_new:
            rows.append(VersionSlideMatch(
                from_slide_id=None, to_slide_id=new_s.id,
                from_version_id=from_version_id, to_version_id=to_version_id,
                match_type="added", score=0.0,
            ))

    # 4) 旧版本中仍未匹配 → deleted
    for old_s in unmatched_old:
        rows.append(VersionSlideMatch(
            from_slide_id=old_s.id, to_slide_id=None,
            from_version_id=from_version_id, to_version_id=to_version_id,
            match_type="deleted", score=0.0,
        ))

    for r in rows:
        db.add(r)
    db.commit()
    logger.info("Matched versions %s -> %s: %d entries", from_version_id, to_version_id, len(rows))
    return len(rows)
