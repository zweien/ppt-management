"""上传路由(UP-01~05)。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.presentation import UploadResponse
from app.services.upload import UploadError, process_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def upload_pptx(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    content = await file.read()
    filename = file.filename or "untitled.pptx"
    try:
        result = process_upload(db, user, filename, content)
    except UploadError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
                            headers={"X-Error-Code": e.code})
    msg = "文件已存在(SHA-256 重复)" if result.is_duplicate else "上传成功"
    from app.schemas.presentation import PresentationOut, VersionOut
    return UploadResponse(
        presentation=PresentationOut(
            id=result.presentation.id,
            title=result.presentation.title,
            page_count=result.presentation.page_count,
            current_version_id=result.presentation.current_version_id,
            deleted_at=result.presentation.deleted_at,
            created_at=result.presentation.created_at,
            current_status=result.version.status,
        ),
        version=VersionOut(
            id=result.version.id,
            presentation_id=result.version.presentation_id,
            version_no=result.version.version_no,
            sha256=result.version.sha256,
            page_count=result.version.page_count,
            status=result.version.status,
            file_size=result.version.file_size,
            original_filename=result.version.original_filename,
            created_at=result.version.created_at,
        ),
        is_duplicate=result.is_duplicate,
        message=msg,
    )
