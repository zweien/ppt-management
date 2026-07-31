"""Open XML 解析(原生结构层,真值,PRD §9.2)。

用 zipfile + lxml 自研,不用 python-pptx 重绘(ADR-0002 / §11.1 精神)。
提取:页面顺序、标题、原生文字、表格、备注、媒体/布局/母版/主题/图表/嵌入等依赖关系。
产出:每页的 slides 记录(page_no/title/native_text/notes_text/content_json/fingerprint)。

content_json 中的 relationships 是为阶段三单页导出(关系图遍历)打基础。
"""
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NSMAP = {"a": A_NS, "r": R_NS, "p": P_NS}


@dataclass
class ParsedSlide:
    page_no: int
    title: str | None = None
    native_text: str = ""
    notes_text: str = ""
    content_json: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedPresentation:
    slides: list[ParsedSlide] = field(default_factory=list)


def _localname(tag: str) -> str:
    return etree.QName(tag).localname


def _extract_text_from_element(el) -> str:
    """Collect all <a:t> text under an element, joining runs/paragraphs."""
    parts: list[str] = []
    for t in el.iter(f"{{{A_NS}}}t"):
        if t.text:
            parts.append(t.text)
    return "".join(parts)


def _extract_paragraphs(el) -> list[str]:
    """Collect paragraphs (a:p) joined within."""
    paras: list[str] = []
    for p in el.iter(f"{{{A_NS}}}p"):
        text = _extract_text_from_element(p)
        if text.strip():
            paras.append(text.strip())
    return paras


def _rel_type_localname(type_uri: str) -> str:
    """Extract localname from a relationship Type URI (e.g. .../relationships/slide -> slide)."""
    if not type_uri:
        return ""
    # relationship types use the form .../relationships/<localname>
    return type_uri.rstrip("/").rsplit("/", 1)[-1]


def _parse_relationships(zf: zipfile.ZipFile, rels_part: str) -> list[dict[str, str]]:
    """Parse a .rels file -> list of {id, type(localname), target, target_mode}."""
    try:
        data = zf.read(rels_part)
    except KeyError:
        return []
    root = etree.fromstring(data)
    rels = []
    for rel in root:
        rid = rel.get("Id", "")
        rtype = _rel_type_localname(rel.get("Type", ""))
        target = rel.get("Target", "")
        mode = rel.get("TargetMode", "Internal")
        rels.append({"id": rid, "type": rtype, "target": target, "target_mode": mode})
    return rels


def parse_pptx(content: bytes) -> ParsedPresentation:
    """Parse a PPTX byte stream into structured slides."""
    zf = zipfile.ZipFile(io.BytesIO(content))
    result = ParsedPresentation()

    # 1. Determine slide order from presentation.xml + presentation.xml.rels
    pres_root = etree.fromstring(zf.read("ppt/presentation.xml"))
    pres_rels = _parse_relationships(zf, "ppt/_rels/presentation.xml.rels")
    rid_to_target = {r["id"]: r["target"] for r in pres_rels}

    slide_rids_in_order: list[str] = []
    for sld_id in pres_root.iter(f"{{{P_NS}}}sldId"):
        rid = sld_id.get(f"{{{R_NS}}}id")
        if rid:
            slide_rids_in_order.append(rid)

    # Map rid -> slide part path
    slide_paths: list[tuple[str, str]] = []  # (path, rid)
    for rid in slide_rids_in_order:
        target = rid_to_target.get(rid, "")
        # normalize relative target (slide1.xml)
        path = "ppt/" + target if not target.startswith("ppt/") else target
        slide_paths.append((path, rid))

    for idx, (slide_path, rid) in enumerate(slide_paths, start=1):
        slide = _parse_slide(zf, slide_path, idx)
        result.slides.append(slide)

    return result


def _parse_slide(zf: zipfile.ZipFile, slide_path: str, page_no: int) -> ParsedSlide:
    try:
        root = etree.fromstring(zf.read(slide_path))
    except KeyError:
        return ParsedSlide(page_no=page_no)

    # Native text: all paragraphs across shapes
    paras = _extract_paragraphs(root)
    native_text = "\n".join(paras)

    # Title: first shape that is a title placeholder (ph type="title" or "ctrTitle")
    title = None
    for ph in root.iter(f"{{{P_NS}}}ph"):
        phtype = ph.get("type", "body")
        if phtype in ("title", "ctrTitle"):
            # climb to sp -> txBody
            sp = ph.getparent().getparent() if ph.getparent() is not None else None
            sp = sp if sp is not None and _localname(sp.tag) == "sp" else ph.getparent()
            txt = _extract_text_from_element(sp) if sp is not None else ""
            if txt.strip():
                title = txt.strip()
                break
    if title is None and paras:
        title = paras[0]

    # Shapes summary (type + text) for content_json
    shapes = []
    for sp in root.iter(f"{{{P_NS}}}sp"):
        sp_text = _extract_text_from_element(sp)
        # determine if placeholder
        ph_el = sp.find(f".//{{{P_NS}}}ph")
        ph_type = ph_el.get("type", "body") if ph_el is not None else None
        shapes.append({"type": "textbox" if ph_type is None else f"placeholder:{ph_type}",
                       "text": sp_text.strip()})
    # Tables
    tables = []
    for tbl in root.iter(f"{{{A_NS}}}tbl"):
        rows = []
        for tr in tbl.iter(f"{{{A_NS}}}tr"):
            cells = [_extract_text_from_element(tc).strip()
                     for tc in tr.iter(f"{{{A_NS}}}tc")]
            rows.append(cells)
        tables.append({"rows": rows})

    # Relationships (dependencies) for this slide — feeds single-slide export (ADR-0002)
    rels_part = slide_path.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    rels = _parse_relationships(zf, rels_part)

    # Pictures(SE-04 元素级索引):遍历 <p:pic> 提取图片元素(rId → target)。
    # rId 从 <a:blip r:embed> 取,target 从本 slide 的 relationships 映射。
    pictures = []
    rid_to_target = {r["id"]: r["target"] for r in rels if r.get("id") and r.get("target")}
    for pic in root.iter(f"{{{P_NS}}}pic"):
        blip = pic.find(f".//{{{A_NS}}}blip")
        if blip is None:
            continue
        rid = blip.get(f"{{{R_NS}}}embed") or blip.get(f"{{{R_NS}}}link")
        if not rid:
            continue
        target = rid_to_target.get(rid)
        # 图片位置(xfrm):x/y/cx/cy(EMU)。供后续高亮/定位(暂不索引,先存 raw)。
        off = pic.find(f".//{{{A_NS}}}off")
        ext = pic.find(f".//{{{A_NS}}}ext")
        pos = {}
        if off is not None:
            pos["x"] = int(off.get("x", 0)); pos["y"] = int(off.get("y", 0))
        if ext is not None:
            pos["cx"] = int(ext.get("cx", 0)); pos["cy"] = int(ext.get("cy", 0))
        pictures.append({
            "rId": rid,
            "target": target,        # 相对路径(如 ../media/image13.png)
            "position": pos or None, # EMU 坐标(可空)
        })

    # Notes
    notes_text = ""
    # notesSlide rel: target usually ../notesSlides/notesSlideN.xml
    notes_rel = next((r for r in rels if r["type"] == "notesSlide"), None)
    if notes_rel:
        notes_path = "ppt/" + notes_rel["target"].replace("../", "")
        notes_path = notes_path.replace("ppt/ppt/", "ppt/")
        try:
            nroot = etree.fromstring(zf.read(notes_path))
            notes_paras = _extract_paragraphs(nroot)
            notes_text = "\n".join(notes_paras)
        except KeyError:
            pass

    content_json = {"shapes": shapes, "tables": tables, "pictures": pictures}

    return ParsedSlide(
        page_no=page_no,
        title=title,
        native_text=native_text,
        notes_text=notes_text,
        content_json=content_json,
        relationships=rels,
    )


def normalize_text_for_fingerprint(text: str) -> str:
    """Normalize native text for fingerprinting (PRD §10.2)."""
    if not text:
        return ""
    t = re.sub(r"\s+", "", text)
    return t.lower()
