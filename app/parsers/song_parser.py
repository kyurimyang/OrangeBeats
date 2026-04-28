# 텍스트/JSON 파싱, 중복 제거, 유효성 판정
# 파싱 방향은 전역 규칙 대신 라인별 dual-case(original/swapped)로 판단한다.

import json
import re
from typing import Any

from app.constants.pipeline_params import (
    CORE_ARTIST_ALIAS_MAP,
    MATCH_NOISE_KEYWORDS,
    MIN_SONG_COUNT,
    MIN_COMPLETE_SONG_COUNT,
    MIN_COMPLETENESS_RATIO,
    NATURAL_SENTENCE_HINTS,
    NON_MUSIC_LINE_PATTERNS,
    PAIR_SEPARATORS,
    SECTION_KEYWORDS,
    TITLE_DELIMITERS,
)

TIME_PREFIX_REGEX = re.compile(r"^\s*(?:\d{1,2}:\d{2}(?::\d{2})?)\s*[-|~>*]*\s*")
TIMESTAMP_TOKEN_REGEX = re.compile(r"(?<!\d)(?:\d{1,2}:\d{2}(?::\d{2})?)(?!\d)")
TIMESTAMP_LINE_REGEX = re.compile(r"^(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<body>.+)$")
TIMESTAMP_PREFIX_ONLY_REGEX = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+")
MULTISPACE_REGEX = re.compile(r"\s+")
BRACKET_REGEX = re.compile(r"[\[\(\{].*?[\]\)\}]")
PARENTHETICAL_REGEX = re.compile(r"[\(\[\{]([^\)\]\}]{1,12})[\)\]\}]")
PAIR_REGEX = re.compile(r".+\s[-|/:~]\s.+")
PURE_PUNCT_REGEX = re.compile(r"^[^\w\uAC00-\uD7A3]+$")
LEADING_DECORATION_REGEX = re.compile(r"^[~*#>+\-\s]+")
TRAILING_DECORATION_REGEX = re.compile(r"[~*#<>\-\s]+$")

SEPARATORS = PAIR_SEPARATORS
KOREAN_NAME_REGEX = re.compile(r"^[\uAC00-\uD7A3]{2,4}$")
ENGLISH_SINGLE_WORD_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9'._-]{1,24}$")
LOWERCASE_ARTIST_HANDLE_REGEX = re.compile(r"^[a-z][a-z0-9._-]{2,24}$")
ARTIST_NAME_WORD_REGEX = re.compile(r"^[A-Z][A-Za-z0-9\'.́éèêëáàäâíìïîóòöôúùüûñ-]{1,}$")
UPPER_ARTIST_TOKEN_REGEX = re.compile(r"^[A-Z0-9]{2,8}$")
REPEATED_HANGUL_TITLE_REGEX = re.compile(r"^([\uAC00-\uD7A3]{1,2})\1{1,}$")

SWAP_GUARD_PENALTY = 1.25
DOMINANT_DIRECTION_RATIO = 0.7
SWAP_SCORE_MARGIN = 0.8
GLOBAL_ARTIST_TITLE_SWAP_MARGIN = 1.2
STRONG_GLOBAL_SWAP_MARGIN = 1.6

TITLE_HINT_KO = [
    "\uc0ac\ub791",
    "\uc774\ubcc4",
    "\uae30\uc5b5",
    "\uc2dc\uac04",
    "\ub9c8\uc74c",
    "\uc624\ub298",
    "\ub0b4\uc77c",
    "\uc6b0\ub9ac",
    "\ub108",
    "\ub098",
    "\uc874\uc7ac",
    "\ucda4",
    "\uc88b\uc544\uc694",
    "\ubd88\ud3b8\ud574",
]
ARTIST_CONNECTORS = ["feat", "ft", "&", ",", " x ", " X "]
TITLE_LEADING_WORDS_EN = {"the", "a", "an", "my", "your", "our", "this", "that"}
TITLE_VERB_HINTS_EN = {"is", "are", "was", "were", "be", "build", "love", "hate", "need", "want"}
TITLE_TRAILING_WORDS_EN = {"mine", "more", "sick", "dance", "umbrella", "vida"}
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


def _strip_timestamps(value: str) -> str:
    value = TIMESTAMP_TOKEN_REGEX.sub(" ", value or "")
    return MULTISPACE_REGEX.sub(" ", value).strip()


def _normalize_parentheses(value: str) -> str:
    return (
        str(value or "")
        .replace("\uff08", "(")
        .replace("\uff09", ")")
        .replace("\uff3b", "[")
        .replace("\uff3d", "]")
        .replace("\uff5b", "{")
        .replace("\uff5d", "}")
    )


def _should_preserve_parenthetical_identifier(value: str, match: re.Match) -> bool:
    content = (match.group(1) or "").strip()
    if not content or re.search(r"\s", content):
        return False
    if not re.fullmatch(r"[A-Za-z0-9]+", content):
        return False

    start, end = match.span()
    prev_char = value[start - 1] if start > 0 else ""
    next_char = value[end] if end < len(value) else ""
    attached_to_identifier = bool(
        re.match(r"[A-Za-z0-9]", prev_char) or re.match(r"[A-Za-z0-9]", next_char)
    )
    if not attached_to_identifier:
        return False

    token_start = start
    while token_start > 0 and not value[token_start - 1].isspace():
        token_start -= 1
    token_end = end
    while token_end < len(value) and not value[token_end].isspace():
        token_end += 1

    token = value[token_start:token_end]
    token_key = re.sub(r"[^A-Za-z0-9]", "", token)
    return 2 <= len(token_key) <= 24 and bool(re.search(r"[A-Za-z]", token_key))


def _strip_bracketed_metadata(value: str) -> str:
    value = _normalize_parentheses(value)

    def replace(match: re.Match) -> str:
        if _should_preserve_parenthetical_identifier(value, match):
            return match.group(0)
        return ""

    return PARENTHETICAL_REGEX.sub(replace, value)


def _has_preserved_parenthetical_identifier(value: str) -> bool:
    value = _normalize_parentheses(value)
    return any(_should_preserve_parenthetical_identifier(value, match) for match in PARENTHETICAL_REGEX.finditer(value))


def _clean_text(value: str) -> str:
    value = str(value or "")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = _strip_bracketed_metadata(value)
    value = TIME_PREFIX_REGEX.sub("", value)
    value = _strip_timestamps(value)
    value = LEADING_DECORATION_REGEX.sub("", value)
    value = TRAILING_DECORATION_REGEX.sub("", value)
    value = MULTISPACE_REGEX.sub(" ", value)
    return value.strip(" -|/:~").strip()


def _normalize_line(line: str) -> str:
    return _clean_text(line)


def _contains_non_music_pattern(line: str) -> bool:
    for pattern in NON_MUSIC_LINE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def _contains_section_keyword(line: str) -> bool:
    lower = line.lower()
    return any(keyword.lower() in lower for keyword in SECTION_KEYWORDS)


def _looks_like_natural_sentence(line: str) -> bool:
    lower = line.lower()
    has_delimiter = any(delimiter in line for delimiter in TITLE_DELIMITERS)
    hint_count = sum(1 for word in NATURAL_SENTENCE_HINTS if word in lower)
    punct_count = sum(lower.count(char) for char in [".", "!", "?", ","])
    word_count = len(lower.split())

    if hint_count >= 2 and not has_delimiter:
        return True
    if punct_count >= 2 and not has_delimiter:
        return True
    if word_count >= 8 and not has_delimiter:
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

    if _contains_section_keyword(normalized) and not any(delimiter in normalized for delimiter in TITLE_DELIMITERS):
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
    return True


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
            return bool(re.search(r"[\-0-9]", word) or word.islower() or len(word) <= 5)

        if (
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


def _shared_artist_alias_hit(text: str) -> bool:
    try:
        from app.services.spotify_common import ARTIST_ALIAS_MAP
    except Exception:
        return False

    normalized = normalize_text(text)
    compact = re.sub(r"[^\w\uAC00-\uD7A3]", "", normalized)
    if not compact:
        return False

    for source, aliases in ARTIST_ALIAS_MAP.items():
        alias_values = aliases if isinstance(aliases, list) else [aliases]
        alias_group = {source, *alias_values}
        alias_keys = {
            re.sub(r"[^\w\uAC00-\uD7A3]", "", normalize_text(alias))
            for alias in alias_group
            if alias
        }
        if compact in alias_keys:
            return True
    return False


def _known_group_artist_hit(text: str) -> bool:
    return normalize_text(text) in KNOWN_GROUP_ARTISTS


def looks_like_artist(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if _contains_artist_hint(cleaned):
        return True
    if _known_group_artist_hit(cleaned):
        return True
    if _artist_alias_hit(cleaned) or _shared_artist_alias_hit(cleaned):
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
    if _artist_alias_hit(cleaned) or _shared_artist_alias_hit(cleaned):
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
        raw_left, raw_right = cleaned.split(sep, 1)
        left, right = raw_left, raw_right
        left = _clean_text(left)
        right = _clean_text(right)
        if left and right:
            return {
                "raw": text,
                "separator": sep,
                "left": left,
                "right": right,
                "artist_parentheses_preserved": _has_preserved_parenthetical_identifier(raw_left),
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


def _count_words(text: str) -> int:
    normalized = normalize_text(text)
    return len(normalized.split()) if normalized else 0


def _compact_len(text: str) -> int:
    return len(re.sub(r"\s+", "", _clean_text(text)))


def _contains_title_phrase_connector(text: str) -> bool:
    normalized = f" {normalize_text(text)} "
    return any(token in normalized for token in [" & ", " + ", " and ", " feat ", " ft ", " with "])


def _has_feature_parenthetical(text: str) -> bool:
    normalized = normalize_text(text)
    return any(token in normalized for token in ["feat", "ft", "with"])


def _looks_like_artist_name_phrase(text: str) -> bool:
    """
    Justin Bieber, Tove Lo, Emotional Oranges, Kendrick Lamar,
    DPR LIVE, SZA, JENNIE 같은 artist-name 형태를 감지한다.
    단, 이 함수만으로 artist를 확정하지 않고 title-artist 판단 보조로만 사용한다.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return False

    normalized = cleaned.replace("́", "")
    parts = [p.strip() for p in re.split(r"\s+", normalized) if p.strip()]

    if not parts or len(parts) > 4:
        return False

    # SZA, JENNIE, DPR LIVE, NCT WISH 같은 대문자 토큰형 artist
    if all(UPPER_ARTIST_TOKEN_REGEX.fullmatch(p.replace(".", "")) for p in parts):
        return True

    # Justin Bieber, Kendrick Lamar, Tove Lo, Emotional Oranges
    capitalized_count = 0
    for part in parts:
        token = part.strip(",.&")
        if ARTIST_NAME_WORD_REGEX.fullmatch(token):
            capitalized_count += 1

    return capitalized_count == len(parts)


def _looks_like_artist_list(text: str) -> bool:
    """
    Chris Brown, Young Thug / Queen Naija, Ari Lennox /
    Kendrick Lamar, SZA 같은 복수 artist 패턴을 감지한다.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return False

    chunks = [chunk.strip() for chunk in re.split(r"\s*,\s*|\s*&\s+|\s+and\s+", cleaned) if chunk.strip()]
    if len(chunks) < 2:
        return False

    return all(_looks_like_artist_name_phrase(chunk) for chunk in chunks)


def _looks_like_title_with_feature_artist(text: str) -> bool:
    """
    Damn Right (feat. Childish Gambino, Kali Uchis)
    Forever (feat. Post Malone, Clever)
    LOYALTY. (feat. Rihanna)
    같은 패턴은 artist가 아니라 title 쪽일 가능성이 높다.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    return _has_feature_parenthetical(cleaned)


def _probable_title_artist_pair(left: str, right: str, global_direction: str = "per_line") -> bool:
    """
    title - artist 패턴을 강하게 감지한다.
    전체 방향이 artist_title로 확정된 경우에는 약한 영어 이름 추정만으로 swap하지 않는다.
    """
    left = _clean_text(left)
    right = _clean_text(right)

    if not left or not right:
        return False

    if global_direction == "artist_title":
        return False

    right_artist_like = (
        _looks_like_artist_list(right)
        or _looks_like_artist_name_phrase(right)
        or _known_group_artist_hit(right)
        or _artist_alias_hit(right)
        or _shared_artist_alias_hit(right)
    )

    left_title_like = (
        _looks_like_title_phrase(left)
        or _looks_like_title_with_feature_artist(left)
        or looks_like_title(left)
    )

    return bool(right_artist_like and left_title_like)


def _looks_like_short_title_candidate(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if len(cleaned) > 32:
        return False

    word_count = _count_words(cleaned)
    if word_count > 4:
        return False

    if looks_like_title(cleaned):
        return True
    return word_count <= 3 and not _contains_artist_hint(cleaned)


def _looks_like_title_phrase(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False

    word_count = _count_words(cleaned)
    if word_count >= 2:
        return True
    if _contains_title_phrase_connector(cleaned):
        return True
    return looks_like_title(cleaned) and not (
        _known_group_artist_hit(cleaned) or _artist_alias_hit(cleaned) or _shared_artist_alias_hit(cleaned)
    )


def _has_artist_identifier_parentheses(text: str) -> bool:
    return _has_preserved_parenthetical_identifier(text)


def _strong_artist_identity_evidence(text: str) -> float:
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0

    evidence = 0.0
    if _artist_alias_hit(cleaned) or _shared_artist_alias_hit(cleaned):
        evidence += 3.0
    if _known_group_artist_hit(cleaned):
        evidence += 2.5
    if _has_artist_identifier_parentheses(cleaned):
        evidence += 2.2
    return round(evidence, 4)


def _known_artist_evidence(text: str) -> float:
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0

    evidence = _strong_artist_identity_evidence(cleaned)
    if _contains_artist_hint(cleaned):
        evidence += 2.0
    if looks_like_english_artist(cleaned):
        evidence += 1.2
    if looks_like_korean_name(cleaned):
        evidence += 0.6
    return round(evidence, 4)


def _title_evidence(text: str) -> float:
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0

    evidence = 0.0
    if _looks_like_title_phrase(cleaned):
        evidence += 1.6
    if looks_like_title_korean(cleaned):
        evidence += 1.2
    if looks_like_title_english(cleaned):
        evidence += 1.0
    if _looks_like_short_title_candidate(cleaned):
        evidence += 0.8
    if _strong_artist_identity_evidence(cleaned) >= 2.5:
        evidence -= 1.8
    return round(evidence, 4)


def _swap_guard_reason(left: str, right: str) -> str:
    # title - artist 구조가 강하면 기존 guard로 swap을 막지 않는다.
    if _probable_title_artist_pair(left, right, "per_line"):
        return ""

    if _strong_artist_identity_evidence(left) >= 2.5:
        return "guard:left_known_artist_evidence"

    if _strong_artist_identity_evidence(right) >= 2.5 and _title_evidence(left) >= 0.8:
        return ""

    # feat/with가 포함된 title은 artist connector로 오해하지 않는다.
    if ("&" in left or "," in left) and not _looks_like_title_with_feature_artist(left):
        return "guard:left_has_artist_connector"

    left_word_count = _count_words(left)
    right_short_title = _looks_like_short_title_candidate(right)
    left_len = _compact_len(left)

    if left_word_count >= 2 and right_short_title and (
        looks_like_english_artist(left)
        or _artist_alias_hit(left)
        or _shared_artist_alias_hit(left)
        or _known_group_artist_hit(left)
    ):
        return "guard:left_name_like_right_short_title"

    if (
        2 <= left_len <= 5
        and _compact_len(right) > left_len
        and (_count_words(right) >= 2 or _contains_title_phrase_connector(right))
        and not _contains_artist_hint(right)
    ):
        return "guard:left_short_artist_like"

    if _looks_like_short_title_candidate(left) and looks_like_english_artist(right):
        return ""

    if _looks_like_title_phrase(right) and not (
        _known_group_artist_hit(right) or _artist_alias_hit(right) or _shared_artist_alias_hit(right)
    ):
        return "guard:right_title_like"

    return ""

def _swap_allowed_by_evidence(
    left: str,
    right: str,
    global_direction: str,
    raw_margin: float,
    adjusted_margin: float,
    swap_margin: float,
) -> tuple[bool, str]:
    left_artist_evidence = _known_artist_evidence(left)
    right_artist_evidence = _known_artist_evidence(right)
    left_strong_artist_evidence = _strong_artist_identity_evidence(left)
    right_strong_artist_evidence = _strong_artist_identity_evidence(right)
    left_title_evidence = _title_evidence(left)
    right_title_evidence = _title_evidence(right)

    # artist_title로 전체 방향이 확정되지 않은 경우,
    # title - artist 패턴이 강하면 swap을 우선 허용한다.
    if global_direction != "artist_title" and _probable_title_artist_pair(left, right, global_direction):
        return True, "swapped:probable_title_artist_pair"

    if left_strong_artist_evidence >= 2.5:
        return False, "original:left_artist_evidence_blocks_swap"
    if right_title_evidence >= 1.6 and right_strong_artist_evidence < 2.5:
        return False, "original:right_title_evidence_blocks_swap"
    if right_strong_artist_evidence >= 2.5 and left_title_evidence >= 0.8 and left_strong_artist_evidence < 2.5:
        return True, "swapped:right_known_artist_left_title_evidence"
    if (
        any(connector in f" {normalize_text(right)} " for connector in [" , ", " feat ", " ft ", " x "])
        and right_artist_evidence >= 2.0
        and left_title_evidence >= 0.8
        and left_strong_artist_evidence < 2.5
    ):
        return True, "swapped:right_artist_connector_left_title_evidence"

    required_margin = swap_margin
    if global_direction == "artist_title":
        required_margin = max(required_margin, STRONG_GLOBAL_SWAP_MARGIN)
        if right_strong_artist_evidence < 2.5:
            return False, "original:global_artist_title_blocks_weak_right_artist"
        if left_title_evidence < 1.2:
            return False, "original:swap_requires_left_title_evidence"
    elif global_direction == "title_artist":
        if right_artist_evidence < 1.2 or left_title_evidence < 0.8:
            return False, "original:weak_title_artist_evidence"
    else:
        if right_artist_evidence < 2.0 or left_title_evidence < 1.0:
            return False, "original:weak_per_line_swap_evidence"

    if raw_margin < required_margin or adjusted_margin < required_margin:
        return False, f"original:swap_margin_too_small({raw_margin:.4f}<{required_margin:.1f})"

    return True, "swapped:right_artist_left_title"


def _build_line_case(case_name: str, artist: str, title: str, score: float, reason: str) -> dict:
    return {
        "case_name": case_name,
        "artist": _clean_text(artist),
        "title": _clean_text(title),
        "score": round(score, 4),
        "reason": reason,
    }


def _select_best_case(left: str, right: str, global_direction: str = "per_line") -> dict:
    detail = _compute_direction_scores(left, right)
    guard_reason = _swap_guard_reason(left, right)

    original_case = _build_line_case(
        "original",
        left,
        right,
        detail["normal_score"],
        "original:left_artist_right_title",
    )

    swapped_adjusted_score = detail["swapped_score"]
    if guard_reason:
        swapped_adjusted_score -= SWAP_GUARD_PENALTY

    swapped_case = _build_line_case(
        "swapped",
        right,
        left,
        swapped_adjusted_score,
        guard_reason or "swapped:right_artist_left_title",
    )

    normalized_global_direction = (
        global_direction if global_direction in {"artist_title", "title_artist"} else "per_line"
    )
    swap_margin = (
        GLOBAL_ARTIST_TITLE_SWAP_MARGIN
        if normalized_global_direction == "artist_title"
        else SWAP_SCORE_MARGIN
    )
    raw_margin = round(detail["swapped_score"] - detail["normal_score"], 4)
    adjusted_margin = round(swapped_case["score"] - original_case["score"], 4)

    if normalized_global_direction in {"artist_title", "title_artist"}:
        chosen = original_case if normalized_global_direction == "artist_title" else swapped_case
        chosen["reason"] = f"{chosen['case_name']}:global_direction_{normalized_global_direction}"
        final_direction = normalized_global_direction
        return {
            "artist": chosen["artist"],
            "title": chosen["title"],
            "chosen_case": chosen["case_name"],
            "score": chosen["score"],
            "reason": chosen["reason"],
            "swap_applied": chosen["case_name"] == "swapped",
            "override_applied": True,
            "swap_guard_applied": bool(guard_reason),
            "swap_guard_reason": guard_reason,
            "left": _clean_text(left),
            "right": _clean_text(right),
            "line_direction": final_direction,
            "final_direction": final_direction,
            "global_direction": normalized_global_direction,
            "direction_score": chosen["score"],
            "normal_score": detail["normal_score"],
            "swapped_score": detail["swapped_score"],
            "adjusted_swapped_score": round(swapped_adjusted_score, 4),
            "swap_margin": swap_margin,
            "score_margin": raw_margin,
            "swap_evidence_reason": "global_direction_override",
            "left_artist_evidence": _known_artist_evidence(left),
            "right_artist_evidence": _known_artist_evidence(right),
            "left_title_evidence": _title_evidence(left),
            "right_title_evidence": _title_evidence(right),
        }

    swap_allowed, evidence_reason = _swap_allowed_by_evidence(
        left,
        right,
        normalized_global_direction,
        raw_margin,
        adjusted_margin,
        swap_margin,
    )

    chosen = original_case
    if not guard_reason and swap_allowed:
        chosen = swapped_case
        swapped_case["reason"] = evidence_reason
    elif guard_reason:
        original_case["reason"] = guard_reason
    elif raw_margin > 0:
        original_case["reason"] = evidence_reason
    else:
        original_case["reason"] = "original:left_artist_right_title"

    final_direction = "title_artist" if chosen["case_name"] == "swapped" else "artist_title"
    return {
        "artist": chosen["artist"],
        "title": chosen["title"],
        "chosen_case": chosen["case_name"],
        "score": chosen["score"],
        "reason": chosen["reason"],
        "swap_applied": chosen["case_name"] == "swapped",
        "override_applied": False,
        "swap_guard_applied": bool(guard_reason),
        "swap_guard_reason": guard_reason,
        "left": _clean_text(left),
        "right": _clean_text(right),
        "line_direction": final_direction,
        "final_direction": final_direction,
        "global_direction": normalized_global_direction,
        "direction_score": chosen["score"],
        "normal_score": detail["normal_score"],
        "swapped_score": detail["swapped_score"],
        "adjusted_swapped_score": round(swapped_adjusted_score, 4),
        "swap_margin": swap_margin,
        "score_margin": raw_margin,
        "swap_evidence_reason": evidence_reason,
        "left_artist_evidence": _known_artist_evidence(left),
        "right_artist_evidence": _known_artist_evidence(right),
        "left_title_evidence": _title_evidence(left),
        "right_title_evidence": _title_evidence(right),
    }


def should_swap(left: str, right: str, global_direction: str = "artist_title") -> tuple[bool, str, dict]:
    finalized = _select_best_case(left, right, global_direction)
    detail = {
        "normal_score": finalized["normal_score"],
        "swapped_score": finalized["swapped_score"],
        "adjusted_swapped_score": finalized["adjusted_swapped_score"],
        "score_margin": finalized["score_margin"],
        "swap_margin": finalized["swap_margin"],
        "swap_guard_applied": finalized["swap_guard_applied"],
        "swap_guard_reason": finalized["swap_guard_reason"],
        "final_direction": finalized["final_direction"],
        "chosen_case": finalized["chosen_case"],
    }
    return finalized["chosen_case"] == "swapped", finalized["reason"], detail


def finalize_pair(left: str, right: str, global_direction: str = "artist_title") -> dict:
    return _select_best_case(left, right, global_direction)


def _safe_log_value(value: str) -> str:
    return str(value or "").replace("'", "\\'")


def _log_parse_line(parsed: dict) -> None:
    print(
        f"[parse-line] raw='{_safe_log_value(parsed.get('raw', ''))}' "
        f"global={parsed.get('global_direction', 'per_line')} "
        f"llm_global={parsed.get('llm_global_direction', 'mixed')} "
        f"llm_confidence={parsed.get('llm_direction_confidence', 'low')} "
        f"chosen_case={parsed.get('chosen_case', 'original')} "
        f"score={float(parsed.get('score', 0.0)):.4f} "
        f"normal={float(parsed.get('normal_score', 0.0)):.4f} "
        f"swapped={float(parsed.get('swapped_score', 0.0)):.4f} "
        f"margin={float(parsed.get('score_margin', 0.0)):.4f} "
        f"swap_guard={str(parsed.get('swap_guard_applied', False)).lower()} "
        f"left='{_safe_log_value(parsed.get('left', ''))}' "
        f"right='{_safe_log_value(parsed.get('right', ''))}' "
        f"artist='{_safe_log_value(parsed.get('artist', ''))}' "
        f"title='{_safe_log_value(parsed.get('title', ''))}' "
        f"reason='{_safe_log_value(parsed.get('reason', ''))}'"
    )


def _resolve_orientation(parts: dict, global_direction: str = "artist_title") -> dict:
    finalized = finalize_pair(parts.get("left", ""), parts.get("right", ""), global_direction)
    finalized["raw"] = parts.get("raw", "")
    if parts.get("artist_parentheses_preserved"):
        finalized["artist_parentheses_preserved"] = True
        reason = finalized.get("reason", "")
        if "artist_parentheses_preserved" not in reason:
            finalized["reason"] = f"{reason}|artist_parentheses_preserved" if reason else "artist_parentheses_preserved"
    return finalized


def _direction_vote(parts: dict) -> str:
    left = parts.get("left", "")
    right = parts.get("right", "")

    # title - artist 패턴을 먼저 감지한다.
    if _probable_title_artist_pair(left, right, "per_line"):
        return "title_artist"

    guard_reason = _swap_guard_reason(left, right)
    if guard_reason:
        return "artist_title"

    detail = _compute_direction_scores(left, right)
    normal_score = detail["normal_score"]
    swapped_score = detail["swapped_score"]

    if normal_score >= swapped_score + SWAP_SCORE_MARGIN:
        return "artist_title"
    if swapped_score >= normal_score + SWAP_SCORE_MARGIN:
        return "title_artist"
    return "unknown"

def _infer_global_direction(parsed_pairs: list[dict]) -> str:
    if not parsed_pairs:
        return "per_line"

    votes = [_direction_vote(parts) for parts in parsed_pairs]
    decisive_votes = [vote for vote in votes if vote in {"artist_title", "title_artist"}]
    if not decisive_votes:
        return "per_line"

    artist_title_count = decisive_votes.count("artist_title")
    title_artist_count = decisive_votes.count("title_artist")
    total = len(decisive_votes)

    if artist_title_count / total >= DOMINANT_DIRECTION_RATIO:
        return "artist_title"
    if title_artist_count / total >= DOMINANT_DIRECTION_RATIO:
        return "title_artist"
    return "per_line"


def _detect_llm_global_direction(parsed_pairs: list[dict]) -> dict:
    fallback = {
        "global_direction": "mixed",
        "confidence": "low",
        "reason": "",
    }
    if not parsed_pairs:
        return fallback

    try:
        from app.services.openai_service import detect_direction_with_llm
    except Exception as exc:
        print("[direction] llm_import_failed =", str(exc))
        return fallback

    pairs = [
        {"left": parts.get("left", ""), "right": parts.get("right", "")}
        for parts in parsed_pairs
        if parts.get("left") and parts.get("right")
    ]

    try:
        detected = detect_direction_with_llm(pairs)
    except Exception as exc:
        print("[direction] llm_call_failed =", str(exc))
        return fallback

    if not isinstance(detected, dict):
        return fallback

    direction = str(detected.get("global_direction") or "mixed").lower().strip()
    confidence = str(detected.get("confidence") or "low").lower().strip()
    reason = str(detected.get("reason") or "").strip()

    if direction not in {"artist_title", "title_artist", "mixed"}:
        direction = "mixed"
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    return {
        "global_direction": direction,
        "confidence": confidence,
        "reason": reason,
    }


def _resolve_global_direction(parsed_pairs: list[dict]) -> tuple[str, dict]:
    rule_direction = _infer_global_direction(parsed_pairs)
    llm_direction = _detect_llm_global_direction(parsed_pairs)
    llm_global_direction = llm_direction.get("global_direction", "mixed")
    llm_confidence = llm_direction.get("confidence", "low")

    if llm_confidence in {"high", "medium"} and llm_global_direction in {"artist_title", "title_artist"}:
        global_direction = llm_global_direction
        source = "llm"
    else:
        global_direction = rule_direction if rule_direction in {"artist_title", "title_artist"} else "per_line"
        source = "rule_fallback"

    print(
        f"[direction] rule={rule_direction} llm={llm_global_direction} "
        f"confidence={llm_confidence} chosen={global_direction} source={source} "
        f"reason='{_safe_log_value(llm_direction.get('reason', ''))}'"
    )

    return global_direction, {
        "llm_global_direction": llm_global_direction,
        "llm_direction_confidence": llm_confidence,
        "llm_direction_reason": llm_direction.get("reason", ""),
        "direction_source": source,
        "rule_global_direction": rule_direction,
    }


def _reuse_existing_direction_meta(songs: list[dict]) -> tuple[str, dict] | None:
    direction_values = {
        str(song.get("global_direction") or "").strip()
        for song in songs
        if isinstance(song, dict) and song.get("global_direction")
    }
    if len(direction_values) != 1:
        return None

    global_direction = next(iter(direction_values))
    if global_direction not in {"artist_title", "title_artist", "per_line"}:
        return None

    sample = next((song for song in songs if isinstance(song, dict) and song.get("global_direction")), {})
    return global_direction, {
        "llm_global_direction": str(sample.get("llm_global_direction") or "mixed"),
        "llm_direction_confidence": str(sample.get("llm_direction_confidence") or "low"),
        "llm_direction_reason": str(sample.get("llm_direction_reason") or ""),
        "direction_source": str(sample.get("direction_source") or "reused"),
        "rule_global_direction": str(sample.get("rule_global_direction") or global_direction),
    }


def _append_song(results: list[dict], artist: str, title: str, meta: dict | None = None) -> None:
    artist = _clean_text(artist)
    title = _clean_text(title)
    meta = meta or {}

    if not _is_meaningful_text(title):
        return

    artist_ok = _is_meaningful_text(artist)
    title_ok = _is_meaningful_text(title)

    completeness_score = 0.0
    if artist_ok:
        completeness_score += 0.5
    if title_ok:
        completeness_score += 0.5

    song = {
        "artist": artist if artist_ok else "",
        "title": title,
        "artist_exists": artist_ok,
        "title_exists": title_ok,
        "is_complete": artist_ok and title_ok,
        "completeness_score": completeness_score,
    }

    for key in [
        "raw",
        "left",
        "right",
        "swap_applied",
        "override_applied",
        "swap_guard_applied",
        "swap_guard_reason",
        "line_direction",
        "final_direction",
        "global_direction",
        "llm_global_direction",
        "llm_direction_confidence",
        "llm_direction_reason",
        "direction_source",
        "rule_global_direction",
        "chosen_case",
        "score",
        "reason",
        "normal_score",
        "swapped_score",
        "adjusted_swapped_score",
        "score_margin",
        "swap_margin",
        "swap_evidence_reason",
        "left_artist_evidence",
        "right_artist_evidence",
        "left_title_evidence",
        "right_title_evidence",
        "artist_parentheses_preserved",
    ]:
        if key in meta:
            song[key] = meta.get(key)

    results.append(song)


def parse_unstructured_lines_to_json(text: str) -> dict:
    if not text:
        return {"songs": []}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pair_candidates = []

    for line in lines:
        if not _is_valid_music_line(line):
            continue

        ts_match = TIMESTAMP_LINE_REGEX.match(line)
        target = _clean_text(ts_match.group("body") if ts_match else line)
        if not target or not _is_valid_music_line(target):
            continue

        parts = _extract_pair_parts(target)
        if not parts:
            continue

        pair_candidates.append(parts)

    global_direction, direction_meta = _resolve_global_direction(pair_candidates)
    results = []
    for parts in pair_candidates:
        parsed = _resolve_orientation(parts, global_direction)
        parsed.update(direction_meta)
        artist = parsed.get("artist", "")
        title = parsed.get("title", "")
        if artist and title:
            _log_parse_line(parsed)
            _append_song(results, artist=artist, title=title, meta=parsed)

    return {"songs": deduplicate_songs(results)}


def normalize_song_candidates(data: Any) -> dict:
    if not data:
        return {"songs": []}

    songs = data.get("songs", []) if isinstance(data, dict) else data
    normalized = []
    pair_candidates = []

    for item in songs:
        if not isinstance(item, dict):
            continue

        artist = _clean_text(item.get("artist", ""))
        title = _clean_text(item.get("title", ""))
        raw = _clean_text(item.get("raw", "")) or f"{artist} - {title}".strip(" -")
        left = _clean_text(item.get("left", artist))
        right = _clean_text(item.get("right", title))
        if left and right:
            pair_candidates.append({"raw": raw, "left": left, "right": right})

    reused_direction = _reuse_existing_direction_meta(songs)
    if reused_direction:
        global_direction, direction_meta = reused_direction
    else:
        global_direction, direction_meta = _resolve_global_direction(pair_candidates)

    for item in songs:
        if not isinstance(item, dict):
            continue

        artist = _clean_text(item.get("artist", ""))
        title = _clean_text(item.get("title", ""))
        raw = _clean_text(item.get("raw", "")) or f"{artist} - {title}".strip(" -")
        left = _clean_text(item.get("left", artist))
        right = _clean_text(item.get("right", title))

        meta = {
            "raw": raw,
            "left": left,
            "right": right,
            "chosen_case": str(item.get("chosen_case") or "original"),
            "score": float(item.get("score") or 0.0),
            "reason": str(item.get("reason") or "provided_artist_title"),
            "swap_applied": bool(item.get("swap_applied", False)),
            "override_applied": False,
            "swap_guard_applied": bool(item.get("swap_guard_applied", False)),
            "swap_guard_reason": str(item.get("swap_guard_reason") or ""),
            "line_direction": "artist_title",
            "final_direction": "artist_title",
            "global_direction": global_direction,
            **direction_meta,
        }

        if left and right:
            parsed = _resolve_orientation({"raw": raw, "left": left, "right": right}, global_direction)
            parsed.update(direction_meta)
            artist = _clean_text(parsed.get("artist", artist))
            title = _clean_text(parsed.get("title", title))
            meta.update(parsed)
            _log_parse_line(parsed)
        elif artist and title:
            # left/right 정보가 없어도 현재 쌍을 독립적으로 재평가한다.
            parsed = _resolve_orientation({"raw": raw, "left": artist, "right": title}, global_direction)
            parsed.update(direction_meta)
            artist = _clean_text(parsed.get("artist", artist))
            title = _clean_text(parsed.get("title", title))
            meta.update(parsed)
        else:
            meta["score"] = max(meta["score"], 0.5 if title else 0.0)

        if not _is_meaningful_text(title):
            continue

        _append_song(normalized, artist=artist, title=title, meta=meta)

    return {"songs": deduplicate_songs(normalized)}


def deduplicate_songs(songs: list[dict]) -> list[dict]:
    best_by_key = {}

    for song in songs:
        key = (
            _clean_text(song.get("artist", "")).lower(),
            _clean_text(song.get("title", "")).lower(),
        )
        prev = best_by_key.get(key)
        if prev is not None and song.get("completeness_score", 0.0) <= prev.get("completeness_score", 0.0):
            continue

        entry = {
            "artist": song.get("artist", ""),
            "title": song.get("title", ""),
            "artist_exists": song.get("artist_exists", False),
            "title_exists": song.get("title_exists", False),
            "is_complete": song.get("is_complete", False),
            "completeness_score": song.get("completeness_score", 0.0),
        }

        for meta_key in [
            "raw",
            "left",
            "right",
            "swap_applied",
            "override_applied",
            "swap_guard_applied",
            "swap_guard_reason",
            "line_direction",
            "final_direction",
            "global_direction",
            "llm_global_direction",
            "llm_direction_confidence",
            "llm_direction_reason",
            "direction_source",
            "rule_global_direction",
            "chosen_case",
            "score",
            "reason",
            "normal_score",
            "swapped_score",
            "adjusted_swapped_score",
            "score_margin",
            "swap_margin",
            "swap_evidence_reason",
            "left_artist_evidence",
            "right_artist_evidence",
            "left_title_evidence",
            "right_title_evidence",
            "artist_parentheses_preserved",
        ]:
            if meta_key in song:
                entry[meta_key] = song.get(meta_key)

        best_by_key[key] = entry

    return list(best_by_key.values())


def count_text_signals(text: str) -> dict:
    if not text:
        return {"timestamp_count": 0, "pattern_count": 0}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    timestamp_count = sum(1 for line in lines if TIMESTAMP_PREFIX_ONLY_REGEX.search(line))
    pattern_count = sum(1 for line in lines if PAIR_REGEX.search(line))
    return {"timestamp_count": timestamp_count, "pattern_count": pattern_count}


def is_text_stage_success(source_text: str, confirmed_tracks: list[dict]) -> bool:
    del source_text
    total = len(confirmed_tracks)
    complete = sum(1 for song in confirmed_tracks if song.get("is_complete"))
    average = (
        sum(song.get("completeness_score", 0.0) for song in confirmed_tracks) / total
        if total
        else 0.0
    )

    return (
        total >= MIN_SONG_COUNT
        and complete >= MIN_COMPLETE_SONG_COUNT
        and average >= MIN_COMPLETENESS_RATIO
    )
