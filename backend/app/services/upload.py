"""上传校验与入库服务(UP-01~05, PRD §6.1 前段, §18.1, §13.2)。

负责:
- 校验:扩展名(.pptx only)/MIME/大小/ZIP 完整性/解压比(防炸弹)
- SHA-256 去重:完全相同文件提示已存在,不生成重复 version
- 不可变落盘到 MinIO(对象键遵循 §13.1)
- 创建 Presentation/Version/Job 记录

注意:本 service 不触发解析/渲染(#04/#05 在 task 层做)。
"""
import hashlib
import io
import zipfile
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import get_storage, source_pptx_key
from app.models import Job, Presentation, PresentationVersion, User

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PPTX_SIG = b"PK\x03\x04"  # ZIP signature


class UploadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class UploadResult:
    presentation: Presentation
    version: PresentationVersion
    is_duplicate: bool
    job: Job


def _validate_pptx(filename: str, content: bytes) -> None:
    # Extension
    lower = filename.lower()
    if not any(lower.endswith(ext) for ext in settings.UPLOAD_ALLOWED_EXTENSIONS):
        raise UploadError("UNSUPPORTED_EXTENSION", f"仅支持 .pptx 文件(不支持 .ppt/加密文件)")
    # Size
    if len(content) > settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise UploadError("FILE_TOO_LARGE", f"文件超过 {settings.UPLOAD_MAX_SIZE_MB}MB 限制")
    # ZIP signature
    if not content.startswith(PPTX_SIG):
        raise UploadError("INVALID_ZIP", "文件不是有效的 PPTX(ZIP)文件")
    # ZIP integrity + bomb check + encryption check
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as e:
        raise UploadError("CORRUPT_ZIP", f"ZIP 文件损坏: {e}") from e
    bad = zf.testzip()
    if bad is not None:
        raise UploadError("CORRUPT_ZIP", f"ZIP 内文件损坏: {bad}")
    # Encryption: pptx may be password-protected; detection via ZipCrypto/WinZip
    for info in zf.infolist():
        if info.flag_bits & 0x1:  # bit 0 = encrypted
            raise UploadError("ENCRYPTED_FILE", "加密文件不支持,请先解密后再上传")
    # Bomb ratio
    total_uncompressed = sum(i.file_size for i in zf.infolist())
    if len(content) > 0:
        ratio = total_uncompressed / len(content)
        if ratio > settings.ZIP_BOMB_RATIO:
            raise UploadError("ZIP_BOMB", f"解压比过高({ratio:.0f}x),疑似 ZIP 炸弹")
    # Must contain presentation.xml to be a real pptx
    names = zf.namelist()
    if "ppt/presentation.xml" not in names or "[Content_Types].xml" not in names:
        raise UploadError("NOT_PPTX", "文件不是有效的 PPTX(缺少 ppt/presentation.xml)")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def process_upload(
    db: Session,
    user: User,
    filename: str,
    content: bytes,
) -> UploadResult:
    """校验、去重、落盘、建记录。"""
    _validate_pptx(filename, content)
    sha = _sha256(content)

    # Dedup: exact-same file already exists (UP-03)
    existing_version = (
        db.query(PresentationVersion)
        .filter(PresentationVersion.sha256 == sha)
        .order_by(PresentationVersion.created_at.desc())
        .first()
    )
    if existing_version is not None:
        pres = db.get(Presentation, existing_version.presentation_id)
        return UploadResult(presentation=pres, version=existing_version, is_duplicate=True, job=None)

    # Create presentation + version
    presentation = Presentation(
        title=_derive_title(filename),
        owner_id=user.id,
        page_count=0,
    )
    db.add(presentation)
    db.flush()  # get id

    version = PresentationVersion(
        presentation_id=presentation.id,
        version_no=1,
        source_object_key="",  # set after storage
        sha256=sha,
        page_count=0,
        status="UPLOADING",
        file_size=len(content),
        original_filename=filename,
    )
    db.add(version)
    db.flush()

    # Store immutably in MinIO (§13.1)
    key = source_pptx_key(presentation.id, version.id)
    storage = get_storage()
    storage.put_object(key, content, content_type=PPTX_MIME)
    version.source_object_key = key
    presentation.current_version_id = version.id

    # Create UPLOADING job (for #09 task center)
    job = Job(
        job_type="validate_pptx",
        target_type="version",
        target_id=version.id,
        status="success",  # validation done synchronously here
        progress=100,
        stage="UPLOADING",
        idempotency_key=f"validate:{version.id}:{sha}",
    )
    db.add(job)
    db.commit()
    db.refresh(presentation)
    db.refresh(version)

    # Trigger parsing pipeline (parse -> render). Graceful if broker down.
    try:
        from app.tasks.basic import parse_openxml_task
        parse_openxml_task.delay(version.id)
    except Exception as e:  # noqa: BLE001
        # Job record exists; user can retry from task center (#09)
        pass

    return UploadResult(presentation=presentation, version=version, is_duplicate=False, job=job)


def _derive_title(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name
