# 텍스트/JSON 파싱, 중복 제거, 성공 판정
# 설명란/LLM 결과를 곡 리스트로 정리

import json
import re
from typing import Any

from app.constants.pipeline_params import (
    MIN_SONG_COUNT,
    MIN_COMPLETE_SONG_COUNT,
    MIN_COMPLETENESS_RATIO,
    SECTION_KEYWORDS,
    NATURAL_SENTENCE_HINTS,
    TITLE_DELIMITERS,
    NON_MUSIC_LINE_PATTERNS,
)

TIME_PREFIX_REGEX = re.compile(r"^\s*(\d{1,2}:\d{2})(?::\d{2})?\s*[-|~>·•]*\s*")
MULTISPACE_REGEX = re.compile(r"\s+")
BRACKET_REGEX = re.compile(r"[\[\(\{].*?[\]\)\}]")
TIMESTAMP_LINE_REGEX = re.compile(r"^(?P<ts>\d{1,2}:\d{2})(?::\d{2})?\s+(?P<body>.+)$")
TIMESTAMP_PREFIX_ONLY_REGEX = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+")
PAIR_REGEX = re.compile(r".+\s[-–—|/:~]\s.+")
PURE_PUNCT_REGEX = re.compile(r"^[^\w가-힣]+$")
LEADING_DECORATION_REGEX = re.compile(r"^[~*#>·•※☆★\-\s]+")
TRAILING_DECORATION_REGEX = re.compile(r"[~*#>·•※☆★\-\s]+$")
SEPARATORS = [" - ", " – ", " — ", " | ", " / ", " : ", " ~ "]


def parse_json_from_text(text: str) -> dict:
    if not text:
        return {"songs": []}

    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"songs": []}

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict) and "songs" in parsed:
            return normalize_song_candidates(parsed)
    except Exception:
        pass

    return {"songs": []}


def _clean_text(value: str) -> str:
    value = str(value or "")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = BRACKET_REGEX.sub("", value)
    value = TIME_PREFIX_REGEX.sub("", value)
    value = LEADING_DECORATION_REGEX.sub("", value)
    value = TRAILING_DECORATION_REGEX.sub("", value)
    value = MULTISPACE_REGEX.sub(" ", value)
    return value.strip(" -–—:|/~").strip()


def _normalize_line(line: str) -> str:
    line = line.strip()
    line = TIME_PREFIX_REGEX.sub("", line)
    line = MULTISPACE_REGEX.sub(" ", line)
    return line.strip()


def _contains_non_music_pattern(line: str) -> bool:
    for pattern in NON_MUSIC_LINE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def _contains_section_keyword(line: str) -> bool:
    lower = line.lower()
    return any(k.lower() in lower for k in SECTION_KEYWORDS)


def _looks_like_natural_sentence(line: str) -> bool:
    lower = line.lower()
    has_delimiter = any(d in line for d in TITLE_DELIMITERS)

    hint = sum(1 for w in NATURAL_SENTENCE_HINTS if w in lower)
    punct = sum(lower.count(p) for p in [".", "!", "?", ","])
    words = len(lower.split())

    if hint >= 2 and not has_delimiter:
        return True
    if punct >= 2 and not has_delimiter:
        return True
    if words >= 8 and not has_delimiter:
        return True

    return False


def _is_valid_music_line(line: str) -> bool:
    if not line or len(line.strip()) < 3:
        return False

    normalized = _normalize_line(line)
    if not normalized:
        return False

    if _contains_non_music_pattern(line) or _contains_non_music_pattern(normalized):
        return False

    if _contains_section_keyword(normalized):
        if not any(d in normalized for d in TITLE_DELIMITERS):
            return False

    if _looks_like_natural_sentence(normalized):
        return False

    return True


def _is_meaningful_text(text: str) -> bool:
    text = _clean_text(text)
    if not text:
        return False
    if PURE_PUNCT_REGEX.fullmatch(text):
        return False
    if re.fullmatch(r"[\d\s]+", text):
        return False
    # '샵' 같은 1글자 아티스트 허용, 단 순수 특수문자는 제외
    return True


def _contains_artist_hint(text: str) -> bool:
    lower = text.lower()
    artist_hints = [
        " feat. ", " feat ", " ft. ", " ft ", " featuring ",
        "prod. ", " prod ", " by ", " x ", " & ", ", "
    ]
    return any(h in f" {lower} " for h in artist_hints)


def _looks_like_artist(text: str) -> bool:
    text = _clean_text(text)
    if not text:
        return False

    if _contains_artist_hint(text):
        return True

    word_count = len(text.split())
    if word_count <= 3 and len(text) <= 24:
        return True

    if len(text) <= 20 and re.fullmatch(r"[A-Za-z0-9&.,'\- ]+", text):
        return True

    return False


def _append_song(results: list[dict], artist: str, title: str):
    artist = _clean_text(artist)
    title = _clean_text(title)

    if not _is_meaningful_text(title):
        return

    artist_ok = _is_meaningful_text(artist)
    title_ok = _is_meaningful_text(title)

    score = 0.0
    if artist_ok:
        score += 0.5
    if title_ok:
        score += 0.5

    results.append({
        "artist": artist if artist_ok else "",
        "title": title,
        "artist_exists": artist_ok,
        "title_exists": title_ok,
        "is_complete": artist_ok and title_ok,
        "completeness_score": score,
    })


def _split_pair(text: str):
    cleaned = _clean_text(text)
    for sep in SEPARATORS:
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            left = _clean_text(left)
            right = _clean_text(right)

            if not left or not right:
                return None

            left_artist_like = _looks_like_artist(left)
            right_artist_like = _looks_like_artist(right)

            if left_artist_like and not right_artist_like:
                return {"artist": left, "title": right}
            if right_artist_like and not left_artist_like:
                return {"artist": right, "title": left}
            # 기본값은 Artist - Title 우선
            return {"artist": left, "title": right}
    return None


def parse_unstructured_lines_to_json(text: str) -> dict:
    if not text:
        return {"songs": []}

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    temp_pairs = []

    for line in lines:
        if not _is_valid_music_line(line):
            continue

        ts_match = TIMESTAMP_LINE_REGEX.match(line)
        target = _clean_text(ts_match.group("body") if ts_match else _normalize_line(line))
        if not target or not _is_valid_music_line(target):
            continue

        parsed = _split_pair(target)
        if parsed:
            temp_pairs.append(parsed)

    results = []
    for item in temp_pairs:
        left = item.get("artist", "")
        right = item.get("title", "")
        if not left or not right:
            continue
        _append_song(results, artist=left, title=right)

    return {"songs": deduplicate_songs(results)}


def normalize_song_candidates(data: Any) -> dict:
    if not data:
        return {"songs": []}

    songs = data.get("songs", []) if isinstance(data, dict) else data
    normalized = []

    for item in songs:
        if not isinstance(item, dict):
            continue

        artist = _clean_text(item.get("artist", ""))
        title = _clean_text(item.get("title", ""))

        # LLM이 artist/title 뒤집어서 낸 흔한 케이스 보정
        if artist and title:
            artist_like = _looks_like_artist(artist)
            title_like = _looks_like_artist(title)
            if not artist_like and title_like:
                artist, title = title, artist

        if not _is_meaningful_text(title):
            continue

        artist_ok = _is_meaningful_text(artist)
        title_ok = _is_meaningful_text(title)

        score = 0.0
        if artist_ok:
            score += 0.5
        if title_ok:
            score += 0.5

        normalized.append({
            "artist": artist if artist_ok else "",
            "title": title,
            "artist_exists": artist_ok,
            "title_exists": title_ok,
            "is_complete": artist_ok and title_ok,
            "completeness_score": score,
        })

    return {"songs": deduplicate_songs(normalized)}


def deduplicate_songs(songs: list[dict]) -> list[dict]:
    best_by_key = {}

    for s in songs:
        key = (
            _clean_text(s.get("artist", "")).lower(),
            _clean_text(s.get("title", "")).lower(),
        )
        prev = best_by_key.get(key)
        if prev is None or s.get("completeness_score", 0.0) > prev.get("completeness_score", 0.0):
            best_by_key[key] = {
                "artist": s.get("artist", ""),
                "title": s.get("title", ""),
                "artist_exists": s.get("artist_exists", False),
                "title_exists": s.get("title_exists", False),
                "is_complete": s.get("is_complete", False),
                "completeness_score": s.get("completeness_score", 0.0),
            }

    return list(best_by_key.values())


def count_text_signals(text: str) -> dict:
    if not text:
        return {"timestamp_count": 0, "pattern_count": 0}

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    t = sum(1 for l in lines if TIMESTAMP_PREFIX_ONLY_REGEX.search(l))
    p = sum(1 for l in lines if PAIR_REGEX.search(l))
    return {"timestamp_count": t, "pattern_count": p}


def is_text_stage_success(source_text: str, confirmed_tracks: list[dict]) -> bool:
    total = len(confirmed_tracks)
    complete = sum(1 for s in confirmed_tracks if s.get("is_complete"))
    avg = (
        sum(s.get("completeness_score", 0.0) for s in confirmed_tracks) / total
        if total else 0.0
    )

    return (
        total >= MIN_SONG_COUNT
        and complete >= MIN_COMPLETE_SONG_COUNT
        and avg >= MIN_COMPLETENESS_RATIO
    )
