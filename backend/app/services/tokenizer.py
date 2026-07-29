"""中文分词(ADR-0004):应用层 jieba + simple 配置 TSVECTOR。

写入与查询共用同一模块与领域词典,保证分词一致。
领域词典从 dict/domain_terms.txt 加载(从 CONTEXT.md glossary 派生)。
"""
import hashlib
import os
from functools import lru_cache

import jieba

_DICT_LOADED = False
_DICT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "dict", "domain_terms.txt")


def _ensure_dict() -> None:
    global _DICT_LOADED
    if _DICT_LOADED:
        return
    path = os.path.abspath(_DICT_PATH)
    if os.path.exists(path):
        jieba.load_userdict(path)
    # Core domain terms (from CONTEXT.md glossary) — ensure good segmentation
    for term in ("智能体簇", "无人系统", "总体架构", "项目申报", "原生文字", "增强文字",
                 "混合检索", "单页", "清华紫", "科技风", "PPTX", "Presentation"):
        jieba.add_word(term)
    _DICT_LOADED = True


def segment(text: str) -> str:
    """Segment text with jieba, return space-joined tokens for simple-config tsvector."""
    if not text:
        return ""
    _ensure_dict()
    tokens = [t.strip() for t in jieba.cut(text) if t.strip()]
    return " ".join(tokens)


def query_segment(query: str) -> str:
    """Segment a search query the same way as document text."""
    return segment(query)


def text_fingerprint_hash(text: str) -> str:
    """Stable hash of the normalized segmented text (used for fingerprint)."""
    seg = segment(text or "")
    return hashlib.sha256(seg.encode()).hexdigest()
