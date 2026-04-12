import re
from typing import Any, Dict, List, Optional


def _normalize_text(value: str) -> str:
    value = (value or "").lower().strip()
    value = value.replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)
    value = re.sub(r"[^\w가-힣\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _clean_track_title_for_search(title: str) -> str:
    value = (title or "").strip()

    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)

    remove_patterns = [
        r"\bfeat\.?.*$",
        r"\bft\.?.*$",
        r"\bwith\b.*$",
        r"\bprod\.?.*$",
        r"\bremaster(ed)?\b.*$",
        r"\blive\b.*$",
        r"\bost\b.*$",
        r"\bver\.?\b.*$",
        r"\bversion\b.*$",
        r"\bsped up\b.*$",
        r"\bslowed\b.*$",
    ]
    for pattern in remove_patterns:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)

    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _artist_variants(artist: Optional[str]) -> List[Optional[str]]:
    if not artist:
        return [None]

    cleaned = artist.strip()
    variants: List[Optional[str]] = [cleaned]

    split_parts = re.split(r"\s*(?:,|&| x | feat\.?|ft\.?)\s*", cleaned, flags=re.IGNORECASE)
    for part in split_parts:
        part = part.strip()
        if part and part not in variants:
            variants.append(part)

    return variants


def _tokenize_text(value: str) -> List[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split() if token]


def _token_overlap_ratio(a: str, b: str) -> float:
    a_tokens = set(_tokenize_text(a))
    b_tokens = set(_tokenize_text(b))

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    denominator = max(len(a_tokens), len(b_tokens))
    if denominator == 0:
        return 0.0

    return round(intersection / denominator, 4)


def _is_suspicious_song(song: Dict[str, Any]) -> bool:
    title = (song.get("title") or "").strip()
    artist = (song.get("artist") or "").strip()

    if not title:
        return True

    if artist and _normalize_text(title) == _normalize_text(artist):
        return True

    return False