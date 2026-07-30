"""Presentation / Version / Slide / Job schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class VersionOut(BaseModel):
    id: str
    presentation_id: str
    version_no: int
    sha256: str
    page_count: int
    status: str
    file_size: int
    original_filename: str
    created_at: datetime
    source_format: str = "pptx"


class PresentationOut(BaseModel):
    id: str
    title: str
    page_count: int
    current_version_id: Optional[str]
    deleted_at: Optional[datetime]
    created_at: datetime
    versions: list[VersionOut] = []
    current_status: Optional[str] = None
    # 解析进度(仅处理中的文件有值,来自当前版本最新的 Job)
    parse_progress: Optional[int] = None
    parse_stage: Optional[str] = None


class SlideOut(BaseModel):
    id: str
    version_id: str
    page_no: int
    title: Optional[str]
    native_text: Optional[str]
    notes_text: Optional[str]
    manual_summary: Optional[str]
    ai_summary: Optional[str]
    preview_object_key: Optional[str]
    thumbnail_object_key: Optional[str]
    parse_status: str
    user_note: Optional[str]
    fingerprint: Optional[str]
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    presentation_title: Optional[str] = None
    is_favorite: bool = False

    @classmethod
    def from_model(
        cls,
        s,
        preview_url: str | None = None,
        thumbnail_url: str | None = None,
        presentation_title: str | None = None,
        is_favorite: bool = False,
    ) -> "SlideOut":
        return cls(
            id=s.id,
            version_id=s.version_id,
            page_no=s.page_no,
            title=s.title,
            native_text=s.native_text,
            notes_text=s.notes_text,
            manual_summary=s.manual_summary,
            ai_summary=s.ai_summary,
            preview_object_key=s.preview_object_key,
            thumbnail_object_key=s.thumbnail_object_key,
            parse_status=s.parse_status,
            user_note=s.user_note,
            fingerprint=s.fingerprint,
            preview_url=preview_url,
            thumbnail_url=thumbnail_url,
            presentation_title=presentation_title,
            is_favorite=is_favorite,
        )


class SlideDetail(SlideOut):
    content_json: Optional[dict[str, Any]] = None
    mineru_markdown: Optional[str] = None
    source_format: str = "pptx"


class JobOut(BaseModel):
    id: str
    job_type: str
    target_type: str
    target_id: str
    status: str
    progress: int
    error_code: Optional[str]
    error_message: Optional[str]
    stage: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    # Resolved target display info (joined for the jobs table, N+1-safe).
    target_name: Optional[str] = None  # version→original_filename; slide→title
    target_parent_name: Optional[str] = None  # owning Presentation.title
    target_parent_id: Optional[str] = None  # owning Presentation.id (for deep links)
    target_page_no: Optional[int] = None  # slide tasks only


class UploadResponse(BaseModel):
    presentation: PresentationOut
    version: VersionOut
    is_duplicate: bool
    message: str


class TagOut(BaseModel):
    id: str
    name: str
    category: Optional[str]
    source: str
    status: str


class SlideTagOut(BaseModel):
    id: str
    tag: TagOut
    origin: str
    confidence: Optional[float]
    is_confirmed: bool
