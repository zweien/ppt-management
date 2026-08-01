"""页面级去重检测(SE-05):全库扫描高度重复/相似页面,归组供治理。

两路相似信号:
- fingerprint(文本规范化哈希,解析时算,覆盖 ~97%):完全相同 → 完全重复组
- visual_phash(64-bit 感知哈希,渲染时算):Hamming 距离 ≤ 阈值 → 高度相似组

聚类:phash 用 union-find(两两距离 ≤ 阈值即同组)。N 小(库级数百页)时
O(N²) 可接受;规模上来后可换 LSH(留 TODO)。

范围:仅当前版本 + 未删除 presentation 的 slide,且按 visibility 过滤。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Presentation, PresentationVersion, Slide

logger = logging.getLogger(__name__)

# 高度相似阈值:64-bit phash 汉明距离 ≤ 8(与版本匹配 PHASH_MODIFIED_THRESHOLD 一致)。
# ≤4 极相似(基本同一页微调),5-8 高相似(同布局小改)。
PHASH_SIMILAR_THRESHOLD = 8


@dataclass
class DupSlideInfo:
    slide_id: str
    page_no: int
    title: str | None
    presentation_id: str
    presentation_title: str | None
    fingerprint: str | None
    visual_phash: str | None
    # 与组代表的 phash 距离(exact 组为 None)
    distance: int | None = None


@dataclass
class DupGroup:
    kind: str  # exact(完全重复) / similar(高度相似)
    slides: list[DupSlideInfo] = field(default_factory=list)


def _visible_current_slides(db: Session, user_id: str | None, superuser: bool) -> list[tuple[Slide, str, str]]:
    """取当前版本 + 未删除 + 可见性过滤的 slide,返回 [(slide, pres_id, pres_title)]。"""
    q = (
        db.query(Slide, Presentation.id, Presentation.title)
        .join(PresentationVersion, Slide.version_id == PresentationVersion.id)
        .join(Presentation, PresentationVersion.presentation_id == Presentation.id)
        .filter(Presentation.deleted_at.is_(None))
        .filter(Presentation.current_version_id == PresentationVersion.id)
    )
    if not superuser and user_id:
        q = q.filter(or_(Presentation.visibility == "team", Presentation.owner_id == user_id))
    return q.all()


def _hamming(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        ia, ib = int(a, 16), int(b, 16)
    except ValueError:
        return None
    return bin(ia ^ ib).count("1")


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def find_duplicate_groups(
    db: Session,
    user_id: str | None = None,
    superuser: bool = False,
    phash_threshold: int = PHASH_SIMILAR_THRESHOLD,
) -> list[DupGroup]:
    """全库扫描,返回重复组列表(exact 在前,similar 在后;组内按 page_no 排序)。

    exact 组:fingerprint 相同且 ≥2 页(跨文件才算;同文件内同 fingerprint 也算——
    同一文件内重复页同样是冗余素材)。
    similar 组:phash 两两距离 ≤ 阈值 union-find 聚类,组 ≥2 页。
    说明:exact 组的成员若也满足 similar 条件,仍各自成组(kind 不同语义不同)。
    """
    rows = _visible_current_slides(db, user_id, superuser)
    info: dict[str, DupSlideInfo] = {}
    for s, pres_id, pres_title in rows:
        info[s.id] = DupSlideInfo(
            slide_id=s.id,
            page_no=s.page_no,
            title=s.title,
            presentation_id=str(pres_id),
            presentation_title=pres_title,
            fingerprint=s.fingerprint,
            visual_phash=s.visual_phash,
        )
    # 空文本页的 fingerprint 是空串哈希,全部相同,会假报完全重复——排除,
    # 这类页交给 phash 判断(similar 组)。
    textless = {sid for sid, s in
                ((sl.id, sl) for sl, _, _ in rows)
                if not (s.native_text or "").strip()}

    groups: list[DupGroup] = []

    # 1) exact:fingerprint 分组(跳过空文本页)
    by_fp: dict[str, list[DupSlideInfo]] = {}
    for it in info.values():
        if it.fingerprint and it.slide_id not in textless:
            by_fp.setdefault(it.fingerprint, []).append(it)
    for fp, members in by_fp.items():
        if len(members) >= 2:
            members.sort(key=lambda m: (m.presentation_title or "", m.page_no))
            groups.append(DupGroup(kind="exact", slides=members))

    # 2) similar:phash union-find 聚类
    phashed = [it for it in info.values() if it.visual_phash]
    uf = _UnionFind()
    dist_to_rep: dict[str, int] = {}
    n = len(phashed)
    for i in range(n):
        for j in range(i + 1, n):
            d = _hamming(phashed[i].visual_phash, phashed[j].visual_phash)
            if d is not None and d <= phash_threshold:
                uf.union(phashed[i].slide_id, phashed[j].slide_id)
    clusters: dict[str, list[DupSlideInfo]] = {}
    for it in phashed:
        root = uf.find(it.slide_id)
        clusters.setdefault(root, []).append(it)
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        # 组代表 = 第一个成员;记录各成员与代表的距离
        rep = members[0]
        for m in members:
            m.distance = _hamming(rep.visual_phash, m.visual_phash)
        members.sort(key=lambda m: (m.distance if m.distance is not None else 99, m.page_no))
        groups.append(DupGroup(kind="similar", slides=members))

    # exact 组在前,组内页数多的在前
    groups.sort(key=lambda g: (0 if g.kind == "exact" else 1, -len(g.slides)))
    return groups


def find_similar_slides(
    db: Session,
    slide_id: str,
    user_id: str | None = None,
    superuser: bool = False,
    phash_threshold: int = PHASH_SIMILAR_THRESHOLD,
    topn: int = 10,
) -> list[DupSlideInfo]:
    """查某页的高度相似页面(详情页提示用)。

    候选:fingerprint 相同(exact,距离视为 0)+ phash 距离 ≤ 阈值。
    按距离升序返回(不含自身)。
    """
    slide = db.get(Slide, slide_id)
    if not slide:
        return []
    # 空文本页的 fingerprint 无区分度(空串哈希),不用于 exact 判定
    slide_has_text = bool((slide.native_text or "").strip())
    rows = _visible_current_slides(db, user_id, superuser)
    out: list[tuple[int, DupSlideInfo]] = []
    for s, pres_id, pres_title in rows:
        if s.id == slide_id:
            continue
        d: int | None = None
        # exact fingerprint → 距离 0(双方都有文本才算)
        if (slide_has_text and (s.native_text or "").strip()
                and slide.fingerprint and s.fingerprint
                and slide.fingerprint == s.fingerprint):
            d = 0
        elif slide.visual_phash and s.visual_phash:
            hd = _hamming(slide.visual_phash, s.visual_phash)
            if hd is not None and hd <= phash_threshold:
                d = hd
        if d is None:
            continue
        out.append((d, DupSlideInfo(
            slide_id=s.id,
            page_no=s.page_no,
            title=s.title,
            presentation_id=str(pres_id),
            presentation_title=pres_title,
            fingerprint=s.fingerprint,
            visual_phash=s.visual_phash,
            distance=d,
        )))
    out.sort(key=lambda x: x[0])
    return [it for _, it in out[:topn]]
