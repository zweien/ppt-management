"""上传路由(UP-01~05 + 版本管理 §10.1)。"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Presentation, PresentationVersion, Slide, User
from app.schemas.presentation import PresentationOut, UploadResponse, VersionOut
from app.services.upload import UploadError, process_upload
from app.services.versioning import suggest_version_candidates

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _version_out(v: PresentationVersion) -> VersionOut:
    return VersionOut(
        id=v.id, presentation_id=v.presentation_id, version_no=v.version_no,
        sha256=v.sha256, page_count=v.page_count, status=v.status,
        file_size=v.file_size, original_filename=v.original_filename, created_at=v.created_at,
        source_format=getattr(v, "source_format", "pptx") or "pptx",
    )


def _pres_out(db: Session, pres: Presentation, cur_status: str | None) -> PresentationOut:
    versions = (
        db.query(PresentationVersion)
        .filter(PresentationVersion.presentation_id == pres.id)
        .order_by(PresentationVersion.version_no)
        .all()
    )
    return PresentationOut(
        id=pres.id, title=pres.title, page_count=pres.page_count,
        current_version_id=pres.current_version_id, deleted_at=pres.deleted_at,
        created_at=pres.created_at, versions=[_version_out(v) for v in versions],
        current_status=cur_status,
    )


@router.post("", response_model=UploadResponse)
async def upload_pptx(
    file: UploadFile = File(...),
    parent_presentation_id: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    """上传 PPTX。parent_presentation_id 非空时作为该文件的新版本(§10.1)。"""
    content = await file.read()
    filename = file.filename or "untitled.pptx"
    try:
        result = process_upload(db, user, filename, content, parent_presentation_id)
    except UploadError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
                            headers={"X-Error-Code": e.code})
    msg = "文件已存在(SHA-256 重复)" if result.is_duplicate else "上传成功"
    db.refresh(result.version)
    return UploadResponse(
        presentation=_pres_out(db, result.presentation, result.version.status),
        version=_version_out(result.version),
        is_duplicate=result.is_duplicate,
        message=msg,
    )


class UploadCheckRequest(BaseModel):
    sha256: str
    size: int | None = None


@router.post("/check")
def check_duplicate(
    body: UploadCheckRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """轻量预检:用客户端算好的 SHA-256 查是否已存在(精确查重),避免重复传输。
    返回 {exists, presentation:{id,title}|null}。仅查未删除 presentation 的版本。
    """
    row = (
        db.query(PresentationVersion)
        .join(Presentation, Presentation.id == PresentationVersion.presentation_id)
        .filter(
            PresentationVersion.sha256 == body.sha256,
            Presentation.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        return {"exists": False, "presentation": None}
    pres = db.get(Presentation, row.presentation_id)
    return {"exists": True, "presentation": {"id": pres.id, "title": pres.title}}


@router.post("/suggest-version")
async def suggest_version(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """[已弃用] 上传前预解析,返回可能的版本候选(指纹 Jaccard,ADR-0008 §1)。

    供前端在上传时给用户"作为新版本"的选项。
    已弃用:该接口需要上传整个文件做相似度计算,与"文件只传一次"冲突。
    前端改用 POST /api/uploads/check(SHA-256 精确查重,轻量)。保留接口向后兼容。
    """
    content = await file.read()
    filename = file.filename or "untitled.pptx"
    from app.services.upload import _validate_pptx
    from app.services.openxml import parse_pptx
    from app.services.tokenizer import text_fingerprint_hash
    try:
        _validate_pptx(filename, content)
    except UploadError as e:
        raise HTTPException(400, e.message, headers={"X-Error-Code": e.code})
    except Exception as e:
        raise HTTPException(400, str(e))
    parsed = parse_pptx(content)
    fps = {text_fingerprint_hash(s.native_text) for s in parsed.slides if s.native_text}
    candidates = suggest_version_candidates(db, fps, len(parsed.slides))
    return {
        "page_count": len(parsed.slides),
        "candidates": [
            {"presentation_id": c.presentation_id, "title": c.title,
             "similarity": c.similarity, "page_count": c.page_count}
            for c in candidates
        ],
    }
