"""Chinese text normalization helpers."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _opencc_converter():
    try:
        from opencc import OpenCC
    except Exception:
        return None
    return OpenCC("t2s")


def to_simplified_chinese(text: str) -> str:
    """Convert Traditional Chinese text to Simplified Chinese when OpenCC is available."""
    if not text:
        return text
    converter = _opencc_converter()
    if not converter:
        return text
    try:
        return converter.convert(text)
    except Exception:
        return text
