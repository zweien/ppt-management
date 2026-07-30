"""MinIO / S3 对象存储客户端(ADR-0001)。

应用只通过对象键访问文件,不在 DB 存大二进制(CONTEXT.md「对象存储抽象」)。
对象键布局遵循 PRD §13.1。
"""
import io
from typing import IO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageClient:
    """S3-compatible (MinIO) client wrapper."""

    def __init__(self) -> None:
        scheme = "https" if settings.MINIO_SECURE else "http"
        # Internal client for server-side put/get operations.
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )
        # External client for generating browser-facing presigned URLs.
        # Must use the external host so the Host header matches the signature (§14.3).
        ext_endpoint = settings.MINIO_EXTERNAL_ENDPOINT or settings.MINIO_ENDPOINT
        self._external_client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{ext_endpoint}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=settings.MINIO_BUCKET)
        except ClientError:
            self._client.create_bucket(Bucket=settings.MINIO_BUCKET)

    def put_object(self, key: str, data: bytes | IO[bytes], content_type: str = "application/octet-stream") -> None:
        if isinstance(data, (bytes, bytearray)):
            data = io.BytesIO(bytes(data))
        self._client.upload_fileobj(data, settings.MINIO_BUCKET, key, ExtraArgs={"ContentType": content_type})

    def get_object(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=settings.MINIO_BUCKET, Key=key)
        return resp["Body"].read()

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=settings.MINIO_BUCKET, Key=key)
            return True
        except ClientError:
            return False

    def presigned_get_url(self, key: str, expires: int = 3600) -> str:
        return self._external_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
            ExpiresIn=expires,
        )


_storage: StorageClient | None = None


def get_storage() -> StorageClient:
    global _storage
    if _storage is None:
        _storage = StorageClient()
    return _storage


# --- Object key layout helpers (PRD §13.1) ---

def source_pptx_key(presentation_id: str, version_id: str) -> str:
    return f"presentations/{presentation_id}/versions/{version_id}/source.pptx"


def source_key(presentation_id: str, version_id: str, ext: str = "pptx") -> str:
    """源文件 object key,保留真实扩展名(LibreOffice 渲染按扩展选 filter)。"""
    ext = ext.lstrip(".") or "pptx"
    return f"presentations/{presentation_id}/versions/{version_id}/source.{ext}"


def preview_pdf_key(presentation_id: str, version_id: str) -> str:
    return f"presentations/{presentation_id}/versions/{version_id}/preview.pdf"


def slide_preview_key(presentation_id: str, version_id: str, page_no: int) -> str:
    return f"presentations/{presentation_id}/versions/{version_id}/slides/{page_no:04d}.png"


def slide_thumb_key(presentation_id: str, version_id: str, page_no: int) -> str:
    return f"presentations/{presentation_id}/versions/{version_id}/slides/{page_no:04d}-thumb.webp"


def ui_logo_key(ext: str = "png") -> str:
    """品牌 logo 对象 key(UI 配置)。"""
    return f"ui/logo.{ext.lstrip('.')}"
