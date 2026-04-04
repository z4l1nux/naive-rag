import re
from typing import Generator

# Separators tried in order — from coarsest to finest grain.
_SEPARATORS = ["\n\n", "\n", ". ", " "]


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Recursive character text splitter.

    Splits `text` into chunks of at most `size` characters, with `overlap`
    characters of context carried over between consecutive chunks.
    Always splits at a natural boundary (paragraph > newline > sentence > word).
    """
    normalized = re.sub(r"\r\n", "\n", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()

    if not normalized:
        return []
    if len(normalized) <= size:
        return [normalized]

    return _split(normalized, _SEPARATORS, size, overlap)


def _split(text: str, separators: list[str], size: int, overlap: int) -> list[str]:
    sep  = separators[0]
    rest = separators[1:]
    parts = text.split(sep)
    chunks: list[str] = []
    current = ""

    for part in parts:
        joined = current + sep + part if current else part

        if len(joined) <= size:
            current = joined
            continue

        if current.strip():
            if len(current) > size and rest:
                chunks.extend(_split(current, rest, size, overlap))
            else:
                chunks.append(current.strip())

        tail = _trailing_overlap(current, sep, overlap)
        current = tail + sep + part if tail else part

    if current.strip():
        if len(current) > size and rest:
            chunks.extend(_split(current, rest, size, overlap))
        else:
            chunks.append(current.strip())

    return [c for c in chunks if len(c.strip()) > 10]


def _trailing_overlap(text: str, sep: str, overlap_size: int) -> str:
    """Return the last `overlap_size` chars trimmed at a separator boundary."""
    if not text or overlap_size <= 0:
        return ""
    tail = text[-overlap_size:]
    boundary = tail.find(sep)
    if boundary > 0:
        return tail[boundary + len(sep):].strip()
    return tail.strip()
