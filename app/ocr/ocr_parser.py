import re
from typing import Dict, List, Optional

from app.parsers.song_parser import _extract_pair_parts, _resolve_orientation


NOISE_KEYWORDS = {
    "subscribe",
    "follow",
    "instagram",
    "insta",
    "playlist",
    "tracklist",
    "comment",
    "like",
    "share",
    "youtube",
    "vol",
    "episode",
    "official",
    "live",
    "mix",
}

SPLIT_PATTERNS = [
    " - ",
    " | ",
    " / ",
    " : ",
    " ~ ",
]


def normalize_text(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def is_noise_text(text: str) -> bool:
    lower_text = text.lower()

    if len(lower_text.strip()) < 3:
        return True

    if any(keyword in lower_text for keyword in NOISE_KEYWORDS):
        return True

    return False


def looks_like_song_line(text: str) -> bool:
    """
    OCR 결과 중 곡 정보 후보처럼 보이는 줄인지 대충 판별
    """
    text = normalize_text(text)
    lower_text = text.lower()

    if not text:
        return False

    if is_noise_text(text):
        return False

    # 00:12 같이 시간 태그가 있으면 후보로 인정
    if re.search(r"\b\d{1,2}:\d{2}\b", lower_text):
        return True

    # artist - title / title - artist 류
    if any(sep in text for sep in SPLIT_PATTERNS):
        return True

    # 너무 긴 문장은 곡 정보일 확률이 낮음
    if len(text) > 80:
        return False

    # 영문/한글 섞인 짧은 줄이면 후보로 볼 여지
    if 4 <= len(text) <= 40:
        return True

    return False


def clean_prefix(text: str) -> str:
    """
    앞 번호, 시간 태그 등 간단 제거
    """
    text = normalize_text(text)

    # [01], (01), 01., 1) 같은 앞 번호 제거
    text = re.sub(r"^\s*[\[\(]?\d{1,2}[\]\)]?[.)]?\s*", "", text)

    # 앞 시간 태그 제거
    text = re.sub(r"^\s*\d{1,2}:\d{2}\s*", "", text)

    return text.strip()


def parse_song_candidate(text: str) -> Optional[Dict]:
    """
    OCR 줄에서 artist/title 후보를 단순 분리
    """
    raw = normalize_text(text)
    cleaned = clean_prefix(raw)

    if not cleaned or is_noise_text(cleaned):
        return None

    parts = _extract_pair_parts(cleaned)
    if parts:
        parsed = _resolve_orientation(parts)
        return {
            "artist": parsed.get("artist"),
            "title": parsed.get("title"),
            "raw": raw,
            "left": parsed.get("left"),
            "right": parsed.get("right"),
            "swap_applied": parsed.get("swap_applied", False),
            "global_direction": parsed.get("global_direction", "per_line"),
            "chosen_case": parsed.get("chosen_case", "original"),
            "score": parsed.get("score", 0.0),
            "reason": parsed.get("reason", ""),
            "swap_guard_applied": parsed.get("swap_guard_applied", False),
            "swap_guard_reason": parsed.get("swap_guard_reason", ""),
            "source": "ocr",
        }

    # 구분자가 없으면 title만 있는 후보로 저장
    return {
        "artist": None,
        "title": cleaned,
        "raw": raw,
        "source": "ocr",
    }


def deduplicate_candidates(candidates: List[Dict]) -> List[Dict]:
    unique = []
    seen = set()

    for item in candidates:
        key = (
            normalize_text(item.get("artist") or "").lower(),
            normalize_text(item.get("title") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique
