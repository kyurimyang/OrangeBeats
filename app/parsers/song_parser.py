# 텍스트/JSON 파싱, 중복 제거, 성공 판정
# 설명란/LLM 결과를 곡 리스트로 정리

import json
import re
from typing import Any

from app.constants.pipeline_params import (
    CORE_ARTIST_ALIAS_MAP,
    GLOBAL_DIRECTION_SAMPLE_SIZE,
    MATCH_NOISE_KEYWORDS,
    MIN_SONG_COUNT,
    MIN_COMPLETE_SONG_COUNT,
    MIN_COMPLETENESS_RATIO,
    PAIR_SEPARATORS,
    SECTION_KEYWORDS,
    NATURAL_SENTENCE_HINTS,
    SWAP_SCORE_MARGIN,
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
SEPARATORS = PAIR_SEPARATORS
KOREAN_NAME_REGEX = re.compile(r"^[\uAC00-\uD7A3]{2,4}$")
ENGLISH_SINGLE_WORD_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9'._-]{1,24}$")
LOWERCASE_ARTIST_HANDLE_REGEX = re.compile(r"^[a-z][a-z0-9._-]{2,24}$")
TITLE_ENDING_HINT_REGEX = re.compile(
    r"(요|데|게|자|밤|꿈|봄|길|꽃|비|춤|사랑|이별|마음|만으로|으로|처럼|인가|거야|없어|같아|했다)$"
)
REPEATED_HANGUL_TITLE_REGEX = re.compile(r"^([\uAC00-\uD7A3]{1,2})\1{1,}$")


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


TITLE_HINT_KO = [
    "\uc0ac\ub791", "\uc774\ubcc4", "\uae30\uc5b5", "\uc2dc\uac04", "\ub9c8\uc74c", "\uc624\ub298", "\ub0b4\uc77c",
    "\uc6b0\ub9ac", "\ub108", "\ub098", "\uc874\uc7ac", "\ucda4", "\uc88b\uc544\uc694", "\ubd88\ud3b8\ud574",
]
ARTIST_CONNECTORS = ["feat", "ft", "&", ",", " x ", " X "]
TITLE_LEADING_WORDS_EN = {"the", "a", "an", "my", "your", "our", "this", "that"}
TITLE_VERB_HINTS_EN = {"is", "are", "was", "were", "be", "build", "love", "hate", "need", "want"}
TITLE_TRAILING_WORDS_EN = {"mine", "more", "sick", "dance", "umbrella", "vida"}
LINE_OVERRIDE_SCORE_MARGIN = 1.0
KNOWN_GROUP_ARTISTS = {
    "shinee",
    "bigbang",
    "2ne1",
    "girls generation",
    "girls' generation",
    "snsd",
    "wonder girls",
    "\uc18c\ub140\uc2dc\ub300",
    "\uc778\ud53c\ub2c8\ud2b8",
    "\ube44\uc2a4\ud2b8",
    "beast",
    "highlight",
}


def normalize_text(text: str) -> str:
    normalized = _clean_text(text).lower()
    normalized = re.sub(r"[^\w\uAC00-\uD7A3\s&.,'\-]", " ", normalized)
    normalized = MULTISPACE_REGEX.sub(" ", normalized)
    return normalized.strip()


def is_hangul_only(text: str) -> bool:
    compact = _clean_text(text).replace(" ", "")
    return bool(compact) and bool(re.fullmatch(r"[\uAC00-\uD7A3]+", compact))


def looks_like_korean_name(text: str) -> bool:
    cleaned = _clean_text(text)
    return bool(cleaned) and bool(KOREAN_NAME_REGEX.fullmatch(cleaned))


def looks_like_english_artist(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    words = normalized.split()
    if len(words) > 3:
        return False
    if any(connector in f" {normalized} " for connector in ARTIST_CONNECTORS):
        return True
    if len(words) == 1 and LOWERCASE_ARTIST_HANDLE_REGEX.fullmatch(normalized):
        return True
    if all(re.fullmatch(r"[a-z0-9&.,'\-]+", word) for word in words):
        if len(words) == 1:
            word = words[0]
            if not ENGLISH_SINGLE_WORD_REGEX.fullmatch(word):
                return False
            # Single-word English artists tend to be handles or stylized short names.
            return bool(re.search(r"[\-0-9]", word) or word.islower() or len(word) <= 5)
        if len(words) >= 2 and (
            words[0] in TITLE_LEADING_WORDS_EN
            or any(word in TITLE_VERB_HINTS_EN for word in words)
            or words[-1] in TITLE_TRAILING_WORDS_EN
        ):
            return False
        return True
    return False


def looks_like_title_korean(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned or not re.search(r"[\uAC00-\uD7A3]", cleaned):
        return False
    if any(hint in cleaned for hint in TITLE_HINT_KO):
        return True
    if REPEATED_HANGUL_TITLE_REGEX.fullmatch(cleaned):
        return True
    if " " in cleaned:
        return True
    if len(cleaned) >= 3 and not looks_like_korean_name(cleaned):
        return True
    return False


def looks_like_title_english(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    words = normalized.split()
    if len(words) >= 2:
        return True
    if len(words) == 1 and len(words[0]) >= 4:
        return True
    return False


def _contains_artist_hint(text: str) -> bool:
    lowered = f" {normalize_text(text)} "
    return any(connector in lowered for connector in ARTIST_CONNECTORS)


def _match_noise_count(text: str) -> int:
    normalized = normalize_text(text)
    return sum(1 for token in MATCH_NOISE_KEYWORDS if token in normalized)


def _artist_alias_hit(text: str) -> bool:
    normalized = normalize_text(text)
    for source, aliases in CORE_ARTIST_ALIAS_MAP.items():
        alias_values = aliases if isinstance(aliases, list) else [aliases]
        alias_group = {normalize_text(source), *(normalize_text(alias) for alias in alias_values)}
        if normalized in alias_group:
            return True
    return False


def _known_group_artist_hit(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in KNOWN_GROUP_ARTISTS


def looks_like_artist(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if _contains_artist_hint(cleaned):
        return True
    if _known_group_artist_hit(cleaned):
        return True
    if _artist_alias_hit(cleaned):
        return True
    if looks_like_korean_name(cleaned):
        return True
    if looks_like_english_artist(cleaned):
        return True
    if is_hangul_only(cleaned) and 2 <= len(cleaned) <= 5:
        return True
    return False


def looks_like_title(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if _known_group_artist_hit(cleaned):
        return False
    if re.search(r"\(.*?\)", cleaned):
        return True
    if looks_like_title_korean(cleaned):
        return True
    if looks_like_title_english(cleaned):
        return True
    return False


def score_artist_like(text: str) -> float:
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0
    score = 0.0
    if looks_like_artist(cleaned):
        score += 1.0
    if _known_group_artist_hit(cleaned):
        score += 1.1
    if looks_like_korean_name(cleaned):
        score += 0.8
    if looks_like_english_artist(cleaned):
        score += 0.8
    if _artist_alias_hit(cleaned):
        score += 0.8
    if _contains_artist_hint(cleaned):
        score += 0.7
    if looks_like_title(cleaned):
        score -= 0.4
    if _match_noise_count(cleaned):
        score -= 0.4
    return round(score, 4)


def score_title_like(text: str) -> float:
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0
    score = 0.0
    if looks_like_title(cleaned):
        score += 1.0
    if looks_like_title_korean(cleaned):
        score += 0.8
    if looks_like_title_english(cleaned):
        score += 0.8
    if _known_group_artist_hit(cleaned):
        score -= 1.0
    if looks_like_korean_name(cleaned):
        score -= 0.5
    if looks_like_english_artist(cleaned):
        score -= 0.5
    if _contains_artist_hint(cleaned):
        score -= 0.4
    return round(score, 4)


def _extract_pair_parts(text: str) -> dict | None:
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    for sep in SEPARATORS:
        if sep not in cleaned:
            continue
        left, right = cleaned.split(sep, 1)
        left = _clean_text(left)
        right = _clean_text(right)
        if left and right:
            return {
                "raw": text,
                "separator": sep,
                "left": left,
                "right": right,
            }
    return None


def _compute_direction_scores(left: str, right: str) -> dict:
    left_artist = score_artist_like(left)
    left_title = score_title_like(left)
    right_artist = score_artist_like(right)
    right_title = score_title_like(right)
    return {
        "left_artist": left_artist,
        "left_title": left_title,
        "right_artist": right_artist,
        "right_title": right_title,
        "normal_score": round(left_artist + right_title, 4),
        "swapped_score": round(right_artist + left_title, 4),
    }


def should_swap(left: str, right: str, global_direction: str = "artist_title") -> tuple[bool, str, dict]:
    detail = _compute_direction_scores(left, right)
    normal_score = detail["normal_score"]
    swapped_score = detail["swapped_score"]

    strong_swapped_signal = looks_like_title(left) and looks_like_artist(right)
    strong_normal_signal = looks_like_artist(left) and looks_like_title(right)
    left_artist_edge = round(detail["left_artist"] - detail["left_title"], 4)
    left_title_edge = round(detail["left_title"] - detail["left_artist"], 4)
    right_artist_edge = round(detail["right_artist"] - detail["right_title"], 4)
    right_title_edge = round(detail["right_title"] - detail["right_artist"], 4)
    right_known_artist = _known_group_artist_hit(right) or _artist_alias_hit(right)
    left_known_artist = _known_group_artist_hit(left) or _artist_alias_hit(left)

    base_direction = global_direction if global_direction in {"artist_title", "title_artist"} else "artist_title"
    final_direction = base_direction
    override_applied = False

    if base_direction == "artist_title":
        if (
            strong_swapped_signal
            and left_title_edge >= 0.8
            and right_artist_edge >= 0.8
            and swapped_score >= normal_score + LINE_OVERRIDE_SCORE_MARGIN
        ):
            final_direction = "title_artist"
            override_applied = True
            reason = "override:left_title_like + right_artist_like"
        else:
            reason = f"follow_global({base_direction})"
    else:
        if (
            strong_normal_signal
            and not right_known_artist
            and (left_known_artist or left_artist_edge >= 0.3)
            and right_title_edge >= 1.2
            and normal_score >= swapped_score + (LINE_OVERRIDE_SCORE_MARGIN + 0.4)
        ):
            final_direction = "artist_title"
            override_applied = True
            reason = "override:left_artist_like + right_title_like"
        else:
            reason = f"follow_global({base_direction})"

    detail["override_applied"] = override_applied
    detail["final_direction"] = final_direction
    detail["margin"] = round(swapped_score - normal_score, 4)
    detail["base_direction"] = base_direction
    detail["left_artist_edge"] = left_artist_edge
    detail["left_title_edge"] = left_title_edge
    detail["right_artist_edge"] = right_artist_edge
    detail["right_title_edge"] = right_title_edge
    return final_direction == "title_artist", reason, detail


def finalize_pair(left: str, right: str, global_direction: str = "artist_title") -> dict:
    swap, reason, detail = should_swap(left, right, global_direction)
    final_direction = detail["final_direction"]
    if final_direction == "title_artist":
        artist, title = right.strip(), left.strip()
        direction_score = detail["swapped_score"]
    else:
        artist, title = left.strip(), right.strip()
        direction_score = detail["normal_score"]
    return {
        "artist": artist,
        "title": title,
        "swap_applied": final_direction == "title_artist",
        "override_applied": detail["override_applied"],
        "reason": reason,
        "left": left,
        "right": right,
        "line_direction": final_direction,
        "final_direction": final_direction,
        "global_direction": global_direction,
        "direction_score": direction_score,
        "normal_score": detail["normal_score"],
        "swapped_score": detail["swapped_score"],
    }


def _safe_log_value(value: str) -> str:
    return str(value or "").replace("'", "\\'")


def _log_parse_line(parsed: dict) -> None:
    print(
        f"[parse-line] raw='{_safe_log_value(parsed.get('raw', ''))}' "
        f"global={parsed.get('global_direction', 'unknown')} "
        f"override={str(parsed.get('override_applied', False)).lower()} "
        f"final_direction={parsed.get('final_direction', parsed.get('line_direction', 'unknown'))} "
        f"left='{_safe_log_value(parsed.get('left', ''))}' "
        f"right='{_safe_log_value(parsed.get('right', ''))}' "
        f"artist='{_safe_log_value(parsed.get('artist', ''))}' "
        f"title='{_safe_log_value(parsed.get('title', ''))}' "
        f"reason='{_safe_log_value(parsed.get('reason', ''))}'"
    )


def _resolve_orientation(parts: dict, global_direction: str = "artist_title") -> dict:
    finalized = finalize_pair(
        parts.get("left", ""),
        parts.get("right", ""),
        global_direction=global_direction,
    )
    finalized["raw"] = parts.get("raw", "")
    return finalized


def _infer_global_direction(parsed_pairs: list[dict]) -> str:
    sample = parsed_pairs[:GLOBAL_DIRECTION_SAMPLE_SIZE]
    if not sample:
        return "unknown"

    normal_votes = 0
    swapped_votes = 0
    normal_total = 0.0
    swapped_total = 0.0
    for parts in sample:
        left = parts.get("left", "")
        right = parts.get("right", "")
        detail = _compute_direction_scores(left, right)
        normal_score = detail["normal_score"]
        swapped_score = detail["swapped_score"]
        normal_total += normal_score
        swapped_total += swapped_score
        if normal_score >= swapped_score + SWAP_SCORE_MARGIN:
            normal_votes += 1
        elif swapped_score >= normal_score + SWAP_SCORE_MARGIN:
            swapped_votes += 1

    if swapped_votes > normal_votes:
        return "title_artist"
    if normal_votes > swapped_votes:
        return "artist_title"
    if swapped_total > normal_total + 0.45:
        return "title_artist"
    if normal_total > swapped_total + 0.45:
        return "artist_title"
    return "artist_title"


def _append_song(results: list[dict], artist: str, title: str, meta: dict | None = None):
    artist = _clean_text(artist)
    title = _clean_text(title)
    meta = meta or {}

    if not _is_meaningful_text(title):
        return

    artist_ok = _is_meaningful_text(artist)
    title_ok = _is_meaningful_text(title)

    score = 0.0
    if artist_ok:
        score += 0.5
    if title_ok:
        score += 0.5

    song = {
        "artist": artist if artist_ok else "",
        "title": title,
        "artist_exists": artist_ok,
        "title_exists": title_ok,
        "is_complete": artist_ok and title_ok,
        "completeness_score": score,
    }
    for key in ["raw", "left", "right", "swap_applied", "override_applied", "line_direction", "final_direction", "global_direction", "reason"]:
        if key in meta:
            song[key] = meta.get(key)
    results.append(song)


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


def _legacy_split_pair_unused(text: str):
    parts = _extract_pair_parts(text)
    if not parts:
        return None
    return _resolve_orientation(parts, global_direction="artist_title")


def _split_pair(text: str):
    parts = _extract_pair_parts(text)
    if not parts:
        return None
    return _resolve_orientation(parts, global_direction="artist_title")


def _legacy_parse_unstructured_lines_to_json_unused(text: str) -> dict:
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


def parse_unstructured_lines_to_json(text: str) -> dict:
    if not text:
        return {"songs": []}

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pair_candidates = []

    for line in lines:
        if not _is_valid_music_line(line):
            continue

        ts_match = TIMESTAMP_LINE_REGEX.match(line)
        target = _clean_text(ts_match.group("body") if ts_match else _normalize_line(line))
        if not target or not _is_valid_music_line(target):
            continue

        parts = _extract_pair_parts(target)
        if parts:
            pair_candidates.append(parts)

    global_direction = _infer_global_direction(pair_candidates)
    results = []
    for parts in pair_candidates:
        parsed = _resolve_orientation(parts, global_direction=global_direction)
        artist = parsed.get("artist", "")
        title = parsed.get("title", "")
        if artist and title:
            _log_parse_line(parsed)
            _append_song(results, artist=artist, title=title, meta=parsed)

    return {"songs": deduplicate_songs(results)}


def _legacy_normalize_song_candidates_unused(data: Any) -> dict:
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
        raw = _clean_text(item.get("raw", "")) or f"{artist} - {title}".strip(" -")
        left = _clean_text(item.get("left", artist))
        right = _clean_text(item.get("right", title))
        global_direction = str(item.get("global_direction") or "artist_title")

        if artist and title:
            parsed = _resolve_orientation(
                {
                    "raw": raw,
                    "left": left,
                    "right": right,
                },
                global_direction=global_direction,
            )
            artist = _clean_text(parsed.get("artist", artist))
            title = _clean_text(parsed.get("title", title))
            meta = parsed
            _log_parse_line(parsed)
        else:
            meta = {
                "raw": raw,
                "left": left,
                "right": right,
                "swap_applied": global_direction == "title_artist",
                "override_applied": False,
                "line_direction": global_direction,
                "final_direction": global_direction,
                "global_direction": global_direction,
                "reason": f"follow_global({global_direction})",
            }

        if not _is_meaningful_text(title):
            continue

        _append_song(normalized, artist=artist, title=title, meta=meta)

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
            entry = {
                "artist": s.get("artist", ""),
                "title": s.get("title", ""),
                "artist_exists": s.get("artist_exists", False),
                "title_exists": s.get("title_exists", False),
                "is_complete": s.get("is_complete", False),
                "completeness_score": s.get("completeness_score", 0.0),
            }
            for meta_key in ["raw", "left", "right", "swap_applied", "override_applied", "line_direction", "final_direction", "global_direction", "reason"]:
                if meta_key in s:
                    entry[meta_key] = s.get(meta_key)
            best_by_key[key] = entry

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
