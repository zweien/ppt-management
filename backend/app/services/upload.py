"""上传校验与入库服务(UP-01~05, PRD §6.1 前段, §18.1, §13.2)。

负责:
- 校验:扩展名/格式(pptx/ppt/pdf)/大小/pptx 的 ZIP 完整性与解压比
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
from app.core.storage import get_storage, source_key
from app.models import Job, Presentation, PresentationVersion, User

# --- 格式常量(magic bytes + MIME) ---
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PPT_MIME = "application/vnd.ms-powerpoint"
PDF_MIME = "application/pdf"
PPTX_SIG = b"PK\x03\x04"  # ZIP signature(OOXML)
OLE2_SIG = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE2/CFB(.ppt 等老 Office)
PDF_SIG = b"%PDF"

FORMAT_MIME = {"pptx": PPTX_MIME, "ppt": PPT_MIME, "pdf": PDF_MIME}


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


def detect_format(filename: str, content: bytes) -> str | None:
    """按 magic bytes 检测格式(pptx/ppt/pdf)。返回 None 表示无法识别。"""
    if content.startswith(PDF_SIG):
        return "pdf"
    if content.startswith(OLE2_SIG):
        # OLE2 复合文档;.ppt 是老 PowerPoint 二进制(也可能是 .doc/.xls,
        # 但扩展名校验已在上游过滤,这里信任扩展名为 .ppt)。
        return "ppt"
    if content.startswith(PPTX_SIG):
        return "pptx"
    return None


def _validate_pptx(filename: str, content: bytes) -> None:
    from app.services.runtime_config import get_upload_extensions, get_upload_max_size_mb, get_zip_bomb_ratio
    # Extension
    lower = filename.lower()
    if not any(lower.endswith(ext) for ext in get_upload_extensions()):
        raise UploadError("UNSUPPORTED_EXTENSION", f"仅支持 .pptx 文件(不支持 .ppt/加密文件)")
    # Size
    max_mb = get_upload_max_size_mb()
    if len(content) > max_mb * 1024 * 1024:
        raise UploadError("FILE_TOO_LARGE", f"文件超过 {max_mb}MB 限制")
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
        if ratio > get_zip_bomb_ratio():
            raise UploadError("ZIP_BOMB", f"解压比过高({ratio:.0f}x),疑似 ZIP 炸弹")
    # Must contain presentation.xml to be a real pptx
    names = zf.namelist()
    if "ppt/presentation.xml" not in names or "[Content_Types].xml" not in names:
        raise UploadError("NOT_PPTX", "文件不是有效的 PPTX(缺少 ppt/presentation.xml)")


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(PDF_SIG):
        raise UploadError("INVALID_PDF", "文件不是有效的 PDF(缺少 %PDF 头)")
    # 尾部应有 %EOF(PDF 结束标记;容忍尾部空白)
    tail = content[-1024:].strip()
    if b"%%EOF" not in tail and b"%EOF" not in tail:
        raise UploadError("INVALID_PDF", "PDF 文件不完整(缺少 %%EOF 结束标记)")


def _validate_ppt(content: bytes) -> None:
    if not content.startswith(OLE2_SIG):
        raise UploadError("INVALID_PPT", "文件不是有效的 .ppt(OLE2 复合文档)")
    # 最小 sanity:OLE2 头之后应有扇区大小等字段(≥ 512 字节);不做完整 BIFF 解析。
    if len(content) < 512:
        raise UploadError("INVALID_PPT", ".ppt 文件过小,可能已损坏")


def _check_size_and_ext(filename: str, content: bytes) -> None:
    """公共校验:扩展名白名单 + 大小上限。"""
    from app.services.runtime_config import get_upload_extensions, get_upload_max_size_mb
    lower = filename.lower()
    if not any(lower.endswith(ext) for ext in get_upload_extensions()):
        raise UploadError("UNSUPPORTED_EXTENSION",
                          f"不支持的文件类型,允许:{','.join(get_upload_extensions())}")
    max_mb = get_upload_max_size_mb()
    if len(content) > max_mb * 1024 * 1024:
        raise UploadError("FILE_TOO_LARGE", f"文件超过 {max_mb}MB 限制")
    if len(content) == 0:
        raise UploadError("INVALID_ZIP", "文件为空")


def _validate_source(filename: str, content: bytes) -> str:
    """统一入口:按 magic bytes 检测格式并做对应校验。返回格式(pptx/ppt/pdf)。
    无法识别抛 UNSUPPORTED_FORMAT。"""
    _check_size_and_ext(filename, content)
    fmt = detect_format(filename, content)
    if fmt == "pptx":
        _validate_pptx(filename, content)
    elif fmt == "pdf":
        _validate_pdf(content)
    elif fmt == "ppt":
        _validate_ppt(content)
    else:
        raise UploadError("UNSUPPORTED_FORMAT", "无法识别的文件格式(仅支持 .pptx / .ppt / .pdf)")
    return fmt


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def process_upload(
    db: Session,
    user: User,
    filename: str,
    content: bytes,
    parent_presentation_id: str | None = None,
) -> UploadResult:
    """校验、去重、落盘、建记录。

    parent_presentation_id 非空时,作为该 presentation 的新版本(version_no 自增),
    而非新建 presentation(版本管理,ADR-0008 / §10.1)。
    """
    _validate_source(filename, content)
    sha = _sha256(content)
    source_format = detect_format(filename, content) or "pptx"

    # Dedup: exact-same file already exists (UP-03)。排除已软删除的文件所属版本。
    existing_version = (
        db.query(PresentationVersion)
        .join(Presentation, Presentation.id == PresentationVersion.presentation_id)
        .filter(
            PresentationVersion.sha256 == sha,
            Presentation.deleted_at.is_(None),
        )
        .order_by(PresentationVersion.created_at.desc())
        .first()
    )
    if existing_version is not None:
        pres = db.get(Presentation, existing_version.presentation_id)
        return UploadResult(presentation=pres, version=existing_version, is_duplicate=True, job=None)

    if parent_presentation_id:
        # 作为已有 presentation 的新版本
        presentation = db.get(Presentation, parent_presentation_id)
        if not presentation or presentation.deleted_at is not None:
            raise UploadError("INVALID_PARENT", "指定的父文件不存在或已删除")
        max_vno = (
            db.query(PresentationVersion.version_no)
            .filter(PresentationVersion.presentation_id == parent_presentation_id)
            .order_by(PresentationVersion.version_no.desc())
            .first()
        )
        next_vno = (max_vno[0] + 1) if max_vno else 1
    else:
        # 新文件
        presentation = Presentation(
            title=_derive_title(filename),
            owner_id=user.id,
            page_count=0,
        )
        db.add(presentation)
        db.flush()
        next_vno = 1

    version = PresentationVersion(
        presentation_id=presentation.id,
        version_no=next_vno,
        source_object_key="",  # set after storage
        sha256=sha,
        page_count=0,
        status="UPLOADING",
        file_size=len(content),
        original_filename=filename,
        source_format=source_format,
    )
    db.add(version)
    db.flush()

    # Store immutably in MinIO (§13.1);key 保留真实扩展名(渲染按扩展选 filter)。
    key = source_key(presentation.id, version.id, source_format)
    storage = get_storage()
    storage.put_object(key, content, content_type=FORMAT_MIME.get(source_format, PPTX_MIME))
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

    # Trigger parsing pipeline. pptx → OpenXML 原生解析(再渲染);
    # ppt/pdf → 直接渲染(render_preview 内按页建空 slide 行,MinerU OCR 填文字)。
    # Graceful if broker down.
    try:
        if source_format == "pptx":
            from app.tasks.basic import parse_openxml_task
            parse_openxml_task.delay(version.id)
        else:
            from app.tasks.render import render_preview_task
            render_preview_task.delay(version.id)
    except Exception as e:  # noqa: BLE001
        # Job record exists; user can retry from task center (#09)
        pass

    return UploadResult(presentation=presentation, version=version, is_duplicate=False, job=job)


def _derive_title(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name
