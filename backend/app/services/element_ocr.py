"""元素级图片 OCR(SE-04):对 slide 内的图片元素单独 OCR,提取文字入索引。

复用 MinerU(已部署,只接受 PDF):图片 → 单页 PDF → MinerU → markdown → 纯文字。
图片字节从 PPTX zip 读(target 是 ../media/xxx 相对路径,需转 zip 内完整路径)。
"""
import io
import logging
import zipfile

from PIL import Image

from app.services.mineru_client import parse_pdf_sync

logger = logging.getLogger(__name__)


def _image_zip_path(slide_path: str, target: str) -> str | None:
    """把 slide rels 的 target(../media/xxx)转成 zip 内完整路径。

    slide_path: ppt/slides/slideN.xml
    target: ../media/image13.png(相对 slides/)
    → ppt/media/image13.png
    """
    if not target:
        return None
    # target 相对 slides/ 目录;../ 退回 ppt/
    if target.startswith("../"):
        return "ppt/" + target[len("../"):]
    return "ppt/slides/" + target


def read_image_bytes_from_pptx(pptx_bytes: bytes, slide_path: str, target: str) -> bytes | None:
    """从 PPTX zip 读指定图片的字节。

    slide_path: ppt/slides/slideN.xml(定位 rels 目录)
    target: 图片相对路径(如 ../media/image13.png)
    """
    zip_path = _image_zip_path(slide_path, target)
    if not zip_path:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as zf:
            return zf.read(zip_path)
    except KeyError:
        logger.warning("image not found in pptx: %s", zip_path)
        return None


def image_bytes_to_pdf(image_bytes: bytes) -> bytes:
    """把图片字节转成单页 PDF(PIL)。供 MinerU(只接受 PDF)OCR。"""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def ocr_image_element(image_bytes: bytes, timeout: float = 120.0) -> str:
    """对单个图片元素 OCR,返回纯文字(markdown 去图片引用)。

    失败返回空串(不阻断解析)。
    """
    try:
        pdf_bytes = image_bytes_to_pdf(image_bytes)
        result = parse_pdf_sync(pdf_bytes, filename="image-element.pdf", timeout=timeout)
        md = result.markdown if hasattr(result, "markdown") else str(result)
        return (md or "").strip()
    except Exception as e:
        logger.warning("image element OCR failed: %s", str(e)[:200])
        return ""
