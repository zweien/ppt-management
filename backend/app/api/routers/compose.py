"""AI 拼 PPT API(SE-06):大纲 → 找素材 → 拼装 PPTX。

认证:X-API-Key(机器)或 SSO session(人)。权限 = key/session 所属用户的可见范围。
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.storage import get_storage
from app.db import get_db
from app.models import ComposeJob, User
from app.services.compose import compose_pptx

router = APIRouter(prefix="/api/compose", tags=["compose"])


class OutlineItem(BaseModel):
    section: str = Field(..., description="大纲节点名,如 封面/背景/架构")
    query: str = Field(..., description="用于检索素材页的关键词/描述")


class ComposeIn(BaseModel):
    title: str = Field(..., max_length=200)
    outline: list[OutlineItem] = Field(..., min_length=1, max_length=60)


class MatchOut(BaseModel):
    section: str
    query: str
    matched: bool
    slide_id: str | None = None
    presentation_title: str | None = None
    page_no: int | None = None
    score: float = 0.0
    hit_reasons: list[str] = []


class ComposeOut(BaseModel):
    compose_id: str
    title: str
    page_count: int
    matched_count: int
    matches: list[MatchOut]
    download_url: str


@router.post("", response_model=ComposeOut, status_code=201)
def compose(body: ComposeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """按大纲找素材并拼装 PPT(同步,秒级)。

    每个 outline 项混合检索取 top1;未命中的项生成占位页并在 matches 标注。
    产出存 MinIO,download_url 可重复下载。
    """
    outline = [{"section": it.section, "query": it.query} for it in body.outline]
    matches, pptx_bytes = compose_pptx(db, body.title.strip(), outline, user)

    job = ComposeJob(
        title=body.title.strip(),
        owner_id=user.id,
        outline=outline,
        matches=[
            {
                "section": m.section, "query": m.query, "matched": m.matched,
                "slide_id": m.slide_id, "presentation_title": m.presentation_title,
                "page_no": m.page_no, "score": m.score, "hit_reasons": m.hit_reasons,
            }
            for m in matches
        ],
        status="done",
    )
    db.add(job)
    db.flush()

    object_key = f"compose/{job.id}/{body.title.strip()}.pptx"
    get_storage().put_object(
        object_key, pptx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    job.object_key = object_key
    db.add(job)
    db.commit()

    matched_count = sum(1 for m in matches if m.matched)
    return ComposeOut(
        compose_id=job.id,
        title=job.title,
        page_count=len(matches),
        matched_count=matched_count,
        matches=[
            MatchOut(
                section=m.section, query=m.query, matched=m.matched,
                slide_id=m.slide_id, presentation_title=m.presentation_title,
                page_no=m.page_no, score=m.score, hit_reasons=m.hit_reasons,
            )
            for m in matches
        ],
        download_url=f"/api/compose/{job.id}/download",
    )


@router.get("/{compose_id}/download")
def download_compose(compose_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """下载拼好的 PPTX。owner 本人或超管。"""
    job = db.get(ComposeJob, compose_id)
    if not job or not job.object_key:
        raise HTTPException(status_code=404, detail="compose 不存在")
    if job.owner_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="forbidden")
    data = get_storage().get_object(job.object_key)
    from urllib.parse import quote
    fname = quote(f"{job.title}.pptx")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"},
    )
