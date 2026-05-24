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
NUMBERED_HYPHEN_TRACK_REGEX = re.compile(r"^\d{1,3}-(.+?)-(.+)$")
TRACK_NUMBER_ONLY_REGEX = re.compile(r"^\s*(?:\d{1,3}|[A-Za-z])[\.)]?\s*$")
TITLE_TRACK_NUMBER_PREFIX_REGEX = re.compile(r"^\s*(?:\d{1,3}|[A-Za-z])\s*[\.)|]\s+")
MULTISPACE_REGEX = re.compile(r"\s+")
BRACKET_REGEX = re.compile(r"[\[\(\{].*?[\]\)\}]")
PARENTHETICAL_REGEX = re.compile(r"[\(\[\{]([^\)\]\}]{1,12})[\)\]\}]")
TITLE_METADATA_HINT_REGEX = re.compile(
    r"[\(\[\{]?\s*(?P<kind>feat|ft|featuring|with|prod(?:uced)?\s+by)\.?\s+(?P<value>[^\)\]\}_/|]{1,80})[\)\]\}]?",
    re.IGNORECASE,
)
PAIR_REGEX = re.compile(r".+\s[-–—|/:~_]\s.+")
PURE_PUNCT_REGEX = re.compile(r"^[^\w\uAC00-\uD7A3]+$")
LEADING_DECORATION_REGEX = re.compile(r"^[~*#>+\-\s]+")
TRAILING_DECORATION_REGEX = re.compile(r"[~*#<>\-\s]+$")
# "Outro : House Of Cards", "EPILOGUE : Young Forever" 같은 앨범 섹션 마커 라인
# → 마커는 버리고 뒤의 곡명만 title-only로 추출
ALBUM_SECTION_MARKER_REGEX = re.compile(
    r"^(?:intro|outro|interlude|epilogue|skit|prologue|prelude|bridge|chapter)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)

SEPARATORS = PAIR_SEPARATORS
KOREAN_NAME_REGEX = re.compile(r"^[\uAC00-\uD7A3]{2,4}$")
ENGLISH_SINGLE_WORD_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9'._-]{1,24}$")
LOWERCASE_ARTIST_HANDLE_REGEX = re.compile(r"^[a-z][a-z0-9._-]{2,24}$")
ARTIST_NAME_WORD_REGEX = re.compile(r"^[A-Z][A-Za-z0-9\'.́éèêëáàäâíìïîóòöôúùüûñ-]{1,}$")
UPPER_ARTIST_TOKEN_REGEX = re.compile(r"^[A-Z0-9]{2,8}$")
REPEATED_HANGUL_TITLE_REGEX = re.compile(r"^([\uAC00-\uD7A3]{1,2})\1{1,}$")

SWAP_GUARD_PENALTY = 0.0
DOMINANT_DIRECTION_RATIO = 0.65
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
LOCAL_SECTION_KEYWORDS = [
    "\uc378\ub124\uc77c",
    "\uc12c\ub124\uc77c",
    "\ub178\ub798 \ubaa8\uc74c",
    "\ub178\ub798\ubaa8\uc74c",
    "\ud50c\ub808\uc774\ub9ac\uc2a4\ud2b8",
    "\ucf00\uc774\ud31d",
    "\uac78\uadf8\ub8f9",
    "\uc5ec\ub3cc",
    "\ub178\ub3d9\uc694",
    "\ub9e4\uc7a5\uc5d0\uc11c \ud2c0\uae30 \uc88b\uc740",
]
PLAYLIST_TITLE_METADATA_KEYWORDS = [
    "playlist",
    "kpop",
    "\ub178\ub798 \ubaa8\uc74c",
    "\ub178\ub798\ubaa8\uc74c",
    "\ud50c\ub808\uc774\ub9ac\uc2a4\ud2b8",
    "\ucf00\uc774\ud31d",
    "\uac78\uadf8\ub8f9",
    "\uc5ec\ub3cc",
    "\ub178\ub3d9\uc694",
]
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


def _strip_title_metadata_phrases(value: str) -> str:
    return TITLE_METADATA_HINT_REGEX.sub(" ", value or "")


def _extract_title_metadata_hints(value: str) -> dict:
    value = _normalize_parentheses(str(value or ""))
    hints = []
    featured_artists = []
    producer_artists = []
    for match in TITLE_METADATA_HINT_REGEX.finditer(value):
        kind = MULTISPACE_REGEX.sub(" ", match.group("kind").lower()).strip()
        raw_value = _clean_text(match.group("value"))
        raw_value = re.split(
            r"\b(?:remix|instrumental|inst|live|remaster(?:ed)?|version|ver)\b",
            raw_value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" -_/:|")
        if not raw_value:
            continue
        hint = f"{kind} {raw_value}"
        if hint not in hints:
            hints.append(hint)
        parts = [
            _clean_text(part)
            for part in re.split(r"\s*(?:,|&| x | and |/)\s*", raw_value, flags=re.IGNORECASE)
            if _clean_text(part)
        ]
        if kind in {"feat", "ft", "featuring", "with"}:
            for part in parts:
                if part not in featured_artists:
                    featured_artists.append(part)
        else:
            for part in parts:
                if part not in producer_artists:
                    producer_artists.append(part)

    return {
        "title_metadata_hints": hints,
        "title_feature_artists": featured_artists,
        "title_producer_artists": producer_artists,
    }


def _has_preserved_parenthetical_identifier(value: str) -> bool:
    value = _normalize_parentheses(value)
    return any(_should_preserve_parenthetical_identifier(value, match) for match in PARENTHETICAL_REGEX.finditer(value))


def _clean_text(value: str) -> str:
    value = str(value or "")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = _strip_title_metadata_phrases(value)
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
    return any(keyword.lower() in lower for keyword in [*SECTION_KEYWORDS, *LOCAL_SECTION_KEYWORDS])


def _looks_like_playlist_title_metadata(line: str) -> bool:
    lower = line.lower()
    keyword_count = sum(1 for keyword in PLAYLIST_TITLE_METADATA_KEYWORDS if keyword in lower)
    slash_count = lower.count("/")
    word_count = len(lower.split())
    bracket_wrapped = bool(re.match(r"^[\[\(\{].{12,}[\]\)\}]?$", line.strip()))

    if keyword_count >= 2 and (bracket_wrapped or slash_count >= 2 or word_count >= 10):
        return True
    if bracket_wrapped and keyword_count >= 1 and word_count >= 8:
        return True
    return False


def _left_part_is_metadata(normalized: str) -> bool:
    """True when the LEFT side of a delimiter contains a section keyword.

    Handles cases like "Playlist 혼자 듣고 싶은 노래 - 중국노래 플레이리스트"
    or "사진 출처 - Weibo @handle" where the left part is a label, not an artist.
    Called only when a delimiter is present (avoids false positives on titled songs).
    """
    for delimiter in TITLE_DELIMITERS:
        if delimiter in normalized:
            left = normalized.split(delimiter, 1)[0].strip()
            if _contains_section_keyword(left):
                return True
            # "from [앨범/곡명] — [아티스트]" 형태의 출처 표기 라인 거부
            # em/en dash 구분자 한정: 일반 " - " 라인은 "From Me to You - Beatles" 같은
            # 정상 트랙 라인과 겹칠 수 있어 제외
            if delimiter in (" — ", " – ") and re.match(r"^from\s+\S", left, re.IGNORECASE):
                return True
            break
    return False


def _looks_like_natural_sentence(line: str) -> bool:
    lower = line.lower()
    has_delimiter = any(delimiter in line for delimiter in TITLE_DELIMITERS)
    hint_count = sum(1 for word in NATURAL_SENTENCE_HINTS if word in lower)
    punct_count = sum(lower.count(char) for char in [".", "?", ","])
    word_count = len(lower.split())

    if hint_count >= 2 and not has_delimiter:
        return True
    # 단어가 1개뿐인 경우 점(.) 2개 이상이어도 문장이 아닌 두문자어(D.D.D, U.S.A)일 수 있음
    if punct_count >= 2 and not has_delimiter and word_count >= 2:
        return True
    if word_count >= 8 and not has_delimiter:
        return True
    return False


def _is_valid_music_line(line: str) -> bool:
    if not line or len(line.strip()) < 2:
        return False

    normalized = _normalize_line(line)
    if not normalized:
        return False

    if _contains_non_music_pattern(line) or _contains_non_music_pattern(normalized):
        return False

    if _looks_like_playlist_title_metadata(normalized):
        return False

    has_delimiter = any(delimiter in normalized for delimiter in TITLE_DELIMITERS)
    if _contains_section_keyword(normalized) and not has_delimiter:
        return False

    # Even with a delimiter: if the left part is a metadata label, reject.
    # e.g. "사진 출처 - Weibo @handle" or "Playlist name - subtitle"
    if has_delimiter and _left_part_is_metadata(normalized):
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


def _strip_underscore_annotation(text: str) -> str:
    """'제목 _ 아티스트' 복합 라인에서 primary separator로 분리된 후 right에 남은 '_ annotation' 제거.
    annotation이 2단어 이하이고 artist-like하며 title-like하지 않을 때만 적용."""
    if " _ " not in text:
        return text
    left_part, annotation = text.split(" _ ", 1)
    annotation = _clean_text(annotation)
    if not annotation:
        return text
    if _count_words(annotation) <= 2 and looks_like_artist(annotation) and not looks_like_title(annotation):
        return _clean_text(left_part)
    return text


def _mask_bracket_spans(text: str) -> tuple[str, dict]:
    """괄호 범위를 placeholder 토큰으로 치환해 split 시 중간 분리를 방지한다."""
    masks: dict[str, str] = {}
    idx = [0]

    def sub(m: re.Match) -> str:
        key = f"\x00M{idx[0]}\x00"
        masks[key] = m.group(0)
        idx[0] += 1
        return key

    return re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", sub, text), masks


def _unmask_bracket_spans(text: str, masks: dict) -> str:
    for key, val in masks.items():
        text = text.replace(key, val)
    return text


def _extract_pair_parts(text: str) -> dict | None:
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    # Normalize "Artist- Title" (no space before hyphen) → "Artist - Title"
    cleaned = re.sub(r"(\w)-\s", r"\1 - ", cleaned)

    for sep in SEPARATORS:
        if sep not in cleaned:
            continue
        raw_left, raw_right = cleaned.split(sep, 1)
        original_left, original_right = (
            text.split(sep, 1) if sep in text else (raw_left, raw_right)
        )
        left, right = raw_left, raw_right
        left = _clean_text(left)
        right = _clean_text(right)
        # '<' 구분자 처리: '[현재아티스트] - [다음아티스트] <[다음곡제목]>' 형식
        # 예: 'BTS - BIGBANG <뱅뱅뱅>' → left='BIGBANG', right='뱅뱅뱅'
        if " <" in right:
            sub_left, sub_right = right.split(" <", 1)
            sub_left = _clean_text(sub_left)
            sub_right = _clean_text(sub_right).rstrip(">").strip()
            if sub_left and sub_right and looks_like_artist(sub_left):
                left = sub_left
                right = sub_right
        # 컴필레이션 포맷: '[이전아티스트] - [다음아티스트] [제목]' (꺽쇠 없이)
        # 예: '베리베리 (VERIVERY) - NCT 127 영웅 (英雄; Kick It)' → artist='NCT 127', title='영웅 (英雄; Kick It)'
        # 오탐 방지: left가 artist로 확정된 경우 right를 재분리하려면
        #   (1) cand_artist가 알려진 아티스트(strong evidence ≥ 2.5), 또는
        #   (2) cand_artist가 2개 이상의 대문자/숫자 토큰 AND cand_title이 CJK 시작이거나 2단어 이상
        # 이 조건 없이 재분리하면 'TREASURE - KING KONG' → artist=KING, title=KONG 같은 오탐 발생.
        elif looks_like_artist(left):
            masked_right, _masks = _mask_bracket_spans(right)
            tokens = masked_right.split()
            for end in range(min(len(tokens) - 1, 4), 0, -1):
                cand_artist = _unmask_bracket_spans(" ".join(tokens[:end]), _masks)
                cand_title = _unmask_bracket_spans(" ".join(tokens[end:]), _masks)
                cand_artist_clean = _clean_text(cand_artist)
                cand_title_clean = _clean_text(cand_title)

                cand_artist_known = _strong_artist_identity_evidence(cand_artist_clean) >= 2.5
                cand_artist_multi_caps = (
                    _count_words(cand_artist_clean) >= 2
                    and all(re.match(r'^[A-Z0-9]+$', t) for t in cand_artist_clean.split()[:2])
                )
                cand_title_strong = bool(
                    cand_title_clean
                    and re.match(r"[가-힣一-鿿぀-ヿ]", cand_title_clean)
                ) or _count_words(cand_title_clean) >= 2

                if not (cand_artist_known or (cand_artist_multi_caps and cand_title_strong)):
                    continue

                if (cand_title
                        and looks_like_artist(cand_artist)
                        and cand_artist[0].isascii()
                        and cand_artist[0].isalpha()
                        and looks_like_title(cand_title)):
                    left = cand_artist
                    right = cand_title
                    break
        # 복합 라인 처리: primary separator가 '_' 아닌데 right에 '_ annotation'이 남은 경우 제거
        # 예: '아티스트 - 제목 _ 원곡아티스트' → right='제목'
        if sep != " _ ":
            right = _strip_underscore_annotation(right)
        nested = _extract_numbered_nested_pair(left, right)
        if nested:
            nested_left, nested_right, nested_sep = nested
            return {
                "raw": text,
                "separator": nested_sep,
                "left": nested_left,
                "right": nested_right,
                "artist_parentheses_preserved": _has_preserved_parenthetical_identifier(nested_left),
                "track_number_prefix": left,
                "nested_pair_extracted": True,
            }
        if left and right:
            return {
                "raw": text,
                "separator": sep,
                "left": left,
                "right": right,
                "artist_parentheses_preserved": _has_preserved_parenthetical_identifier(raw_left),
                "left_title_metadata": _extract_title_metadata_hints(original_left),
                "right_title_metadata": _extract_title_metadata_hints(original_right),
            }
    # 폴백: '[아티스트] <[제목]>' 형식 (primary separator 없이 '<'만 있는 경우)
    # 예: '샤이니 (SHINee) <Don't Call Me>' → artist='샤이니 (SHINee)', title='Don't Call Me'
    if " <" in cleaned:
        sub_left, sub_right = cleaned.split(" <", 1)
        sub_left = _clean_text(sub_left)
        sub_right = _clean_text(sub_right).rstrip(">").strip()
        # 한글 아티스트 판별: '블락비 (Block B)' 같이 영문 병기가 붙은 경우도 처리
        compact_base = re.sub(r"\s*\([^)]*\)\s*", "", sub_left).replace(" ", "")
        is_hangul_artist = bool(re.fullmatch(r"[가-힣]+", compact_base)) and 2 <= len(compact_base) <= 15
        if sub_left and sub_right and (looks_like_artist(sub_left) or is_hangul_artist):
            return {
                "raw": text,
                "separator": " <",
                "left": sub_left,
                "right": sub_right,
                "artist_parentheses_preserved": _has_preserved_parenthetical_identifier(sub_left),
                "left_title_metadata": {},
                "right_title_metadata": {},
            }
    return None


def _looks_like_track_number_prefix(text: str) -> bool:
    cleaned = _clean_text(text)
    return bool(cleaned and TRACK_NUMBER_ONLY_REGEX.fullmatch(cleaned))


def _extract_numbered_hyphen_track(text: str) -> dict | None:
    """01-KiiiKiii-404, 13-NewJeans-Super Shy 같이 NN-Artist-Title 형식을 처리한다."""
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    match = NUMBERED_HYPHEN_TRACK_REGEX.match(cleaned)
    if not match:
        return None
    artist = _clean_text(match.group(1))
    title = _clean_text(match.group(2))
    if not artist or not title:
        return None
    return {
        "raw": text,
        "left": artist,
        "right": title,
        "artist": artist,
        "title": title,
        "_numbered_track": True,
    }


def _extract_bare_hyphen_pair(text: str) -> dict | None:
    """타임스탬프 라인에서 'Artist-Title' (공백 없는 하이픈) 형식을 처리한다.
    PAIR_SEPARATORS(공백 있는 구분자)로 분리 실패 시 fallback으로만 호출된다."""
    cleaned = _clean_text(text)
    if not cleaned or "-" not in cleaned:
        return None
    if any(sep in cleaned for sep in SEPARATORS):
        return None
    raw_left, raw_right = cleaned.split("-", 1)
    left = _clean_text(raw_left)
    right = _clean_text(raw_right)
    if not left or not right:
        return None
    return {
        "raw": text,
        "separator": "-",
        "left": left,
        "right": right,
        "artist_parentheses_preserved": _has_preserved_parenthetical_identifier(raw_left),
        "left_title_metadata": _extract_title_metadata_hints(raw_left),
        "right_title_metadata": _extract_title_metadata_hints(raw_right),
    }


def _extract_numbered_nested_pair(left: str, right: str) -> tuple[str, str, str] | None:
    if not _looks_like_track_number_prefix(left):
        return None

    cleaned_right = _clean_text(right)
    if not cleaned_right:
        return None

    for sep in SEPARATORS:
        if sep not in cleaned_right:
            continue
        nested_left, nested_right = cleaned_right.split(sep, 1)
        nested_left = _clean_text(nested_left)
        nested_right = _clean_text(nested_right)
        if nested_left and nested_right and not _looks_like_track_number_prefix(nested_left):
            return nested_left, nested_right, sep

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

    # 단일 단어 right는 "Woman", "Obsessed" 같은 제목 단어도 _looks_like_artist_name_phrase를 통과하므로
    # alias/known group 같은 추가 근거 없이는 아티스트로 판정하지 않음
    _right_has_extra_artist_signal = (
        _known_group_artist_hit(right)
        or _artist_alias_hit(right)
        or _shared_artist_alias_hit(right)
        or _contains_artist_hint(right)
    )
    right_artist_like = (
        _looks_like_artist_list(right)
        or _right_has_extra_artist_signal
        or (
            _looks_like_artist_name_phrase(right)
            and (_count_words(right) >= 2 or _right_has_extra_artist_signal)
        )
    )

    left_title_like = (
        _looks_like_title_phrase(left)
        or _looks_like_title_with_feature_artist(left)
        or looks_like_title(left)
    )

    # 단일 이름 아티스트(IU, 태연, 헤이즈 등)는 2단어 조건을 못 채워 right_artist_like가
    # False로 떨어지는 문제 보완. 왼쪽에 강한 제목 근거(1.2+)가 있으면 단일 이름도 허용.
    if (
        not right_artist_like
        and _looks_like_artist_name_phrase(right)
        and _count_words(right) == 1
        and not _contains_artist_hint(right)
        and _title_evidence(left) >= 1.2
    ):
        right_artist_like = True

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
    if swap_allowed:
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
    title_side = "left" if finalized.get("title") == parts.get("left", "") else "right"
    metadata = parts.get(f"{title_side}_title_metadata") or {}
    for key in ["title_metadata_hints", "title_feature_artists", "title_producer_artists"]:
        if metadata.get(key):
            finalized[key] = metadata.get(key)
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
    if re.fullmatch(r"[A-Z0-9]{1,4}", right or "") and re.search(r"[\uAC00-\uD7A3]", left or "") and len(left) >= 4:
        return "artist_title"

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
    artist = TITLE_TRACK_NUMBER_PREFIX_REGEX.sub("", artist).strip()
    title = _clean_text(title)
    title = TITLE_TRACK_NUMBER_PREFIX_REGEX.sub("", title).strip()
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

    if bool(meta.get("swap_applied")):
        song["original_input"] = {
            "artist": _clean_text(meta.get("left", "")),
            "title": _clean_text(meta.get("right", "")),
        }
        song["corrected_input"] = {
            "artist": artist if artist_ok else "",
            "title": title,
        }
        song["normalized_by"] = "swap_detected"

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
        "track_number_prefix",
        "nested_pair_extracted",
        "timestamp",
        "source",
        "source_mode",
        "original_input",
        "corrected_input",
        "normalized_by",
        "artist_inferred",
        "inferred_artist_source",
        "title_metadata_hints",
        "title_feature_artists",
        "title_producer_artists",
        "raw_line",
        "line_index",
        "confidence",
        "evidence_type",
        "reject_reason",
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
        raw_target = ts_match.group("body") if ts_match else line
        target = _clean_text(raw_target)
        if not target or not _is_valid_music_line(target):
            continue

        # 앨범 섹션 마커 우선 처리: "Outro : House Of Cards" → 분리 차단, 전체가 곡명
        # "Outro: House of Cards", "EPILOGUE: Young Forever" 같이 마커 포함이 공식 제목임
        album_section_match = ALBUM_SECTION_MARKER_REGEX.match(raw_target)
        if album_section_match:
            parts = {
                "raw": raw_target,
                "left": "",
                "right": "",
                "_title_only": True,
                # _section_marker_title 없음 → 아래 title-only 처리에서 parts["raw"] 전체를 제목으로 사용
            }
        else:
            parts = _extract_pair_parts(raw_target)
            if not parts:
                parts = _extract_numbered_hyphen_track(raw_target)
            if not parts and ts_match:
                parts = _extract_bare_hyphen_pair(raw_target)
            if not parts:
                # 타임스탬프가 있는데 구분자가 없으면 body 전체를 title-only로 보관
                if ts_match:
                    parts = {"raw": raw_target, "left": "", "right": "", "_title_only": True}
                else:
                    continue

        if ts_match:
            parts["_timestamp"] = ts_match.group("ts")
        pair_candidates.append(parts)

    pair_candidates_with_sep = [
        p for p in pair_candidates
        if not p.get("_title_only") and not p.get("_numbered_track")
    ]
    global_direction, direction_meta = _resolve_global_direction(pair_candidates_with_sep)
    results = []
    for parts in pair_candidates:
        # 타임스탬프 + 제목만 있는 줄: artist는 inferred_artist에서 채워질 예정
        # 섹션 마커 라인("Outro : House Of Cards")은 _section_marker_title을 우선 사용
        if parts.get("_title_only"):
            title = _clean_text(parts.get("_section_marker_title") or parts["raw"])
            if title:
                meta: dict = {"_title_only": True}
                if parts.get("_timestamp"):
                    meta["timestamp"] = parts["_timestamp"]
                _append_song(results, artist="", title=title, meta=meta)
            continue

        # NN-Artist-Title 형식: 방향이 확정되어 있으므로 orientation 로직 건너뜀
        # "404" 같은 숫자 제목도 유효하므로 _is_meaningful_text 필터를 우회해 직접 추가
        if parts.get("_numbered_track"):
            artist = parts.get("artist", "")
            title = parts.get("title", "")
            if artist and title:
                entry: dict = {
                    "artist": artist,
                    "title": title,
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                    "_numbered_track": True,
                    "raw": parts.get("raw", ""),
                }
                if parts.get("_timestamp"):
                    entry["timestamp"] = parts["_timestamp"]
                results.append(entry)
            continue

        line_direction = "title_artist" if parts.get("nested_pair_extracted") else global_direction
        parsed = _resolve_orientation(parts, line_direction)
        parsed.update(direction_meta)
        if parts.get("nested_pair_extracted"):
            parsed["nested_pair_extracted"] = True
            parsed["track_number_prefix"] = parts.get("track_number_prefix", "")
        artist = parsed.get("artist", "")
        title = parsed.get("title", "")
        if artist and title:
            if parts.get("_timestamp"):
                parsed["timestamp"] = parts["_timestamp"]
            _log_parse_line(parsed)
            _append_song(results, artist=artist, title=title, meta=parsed)

    return {"songs": deduplicate_songs(results)}


def normalize_song_candidates(data: Any, inferred_artist: str = "") -> dict:
    if not data:
        return {"songs": []}

    inferred_artist = _clean_text(inferred_artist)
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
        for hint_key in ["title_metadata_hints", "title_feature_artists", "title_producer_artists"]:
            if item.get(hint_key):
                meta[hint_key] = item.get(hint_key)
        for evidence_key in ["raw_line", "line_index", "confidence", "evidence_type", "reject_reason"]:
            if evidence_key in item:
                meta[evidence_key] = item.get(evidence_key)

        if left and right:
            line_direction = "title_artist" if item.get("nested_pair_extracted") else global_direction
            parsed = _resolve_orientation(
                {
                    "raw": raw,
                    "left": left,
                    "right": right,
                    "left_title_metadata": item.get("left_title_metadata", {}),
                    "right_title_metadata": item.get("right_title_metadata", {}),
                },
                line_direction,
            )
            parsed.update(direction_meta)
            if item.get("nested_pair_extracted"):
                parsed["nested_pair_extracted"] = True
                parsed["track_number_prefix"] = item.get("track_number_prefix", "")
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

        if not artist and inferred_artist:
            artist = inferred_artist
            meta["artist_inferred"] = True
            meta["inferred_artist_source"] = str(item.get("inferred_artist_source") or "single_artist_context")
            meta["reason"] = str(meta.get("reason") or "provided_artist_title")

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
            "track_number_prefix",
            "nested_pair_extracted",
            "timestamp",
            "source",
            "source_mode",
            "original_input",
            "corrected_input",
            "normalized_by",
            "artist_inferred",
            "inferred_artist_source",
            "title_metadata_hints",
            "title_feature_artists",
            "title_producer_artists",
            "raw_line",
            "line_index",
            "confidence",
            "evidence_type",
            "reject_reason",
        ]:
            if meta_key in song:
                entry[meta_key] = song.get(meta_key)

        best_by_key[key] = entry

    return list(best_by_key.values())


def count_text_signals(text: str) -> dict:
    if not text:
        return {
            "timestamp_count": 0,
            "pattern_count": 0,
            "candidate_line_count": 0,
            "line_count": 0,
            "candidate_line_ratio": 0.0,
            "has_tracklist_structure": False,
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    timestamp_count = sum(1 for line in lines if TIMESTAMP_PREFIX_ONLY_REGEX.search(line))
    pattern_count = sum(1 for line in lines if PAIR_REGEX.search(line))
    candidate_line_count = sum(1 for line in lines if _is_valid_music_line(line) and (TIMESTAMP_PREFIX_ONLY_REGEX.search(line) or PAIR_REGEX.search(line)))
    candidate_line_ratio = candidate_line_count / max(len(lines), 1)
    has_tracklist_structure = (
        timestamp_count >= 2
        or pattern_count >= 2
        or candidate_line_ratio >= 0.35
        or any(_contains_section_keyword(line) for line in lines)
    )
    return {
        "timestamp_count": timestamp_count,
        "pattern_count": pattern_count,
        "candidate_line_count": candidate_line_count,
        "line_count": len(lines),
        "candidate_line_ratio": round(candidate_line_ratio, 3),
        "has_tracklist_structure": has_tracklist_structure,
    }


def is_text_stage_success(source_text: str, confirmed_tracks: list[dict]) -> bool:
    return assess_text_stage_validity(source_text, confirmed_tracks)["success"]


def assess_text_stage_validity(source_text: str, confirmed_tracks: list[dict]) -> dict:
    total = len(confirmed_tracks)
    complete = sum(1 for song in confirmed_tracks if song.get("is_complete"))
    average = (
        sum(song.get("completeness_score", 0.0) for song in confirmed_tracks) / total
        if total
        else 0.0
    )
    signals = count_text_signals(source_text or "")
    strong_pattern = (
        signals.get("timestamp_count", 0) >= 2
        or signals.get("pattern_count", 0) >= 2
        or signals.get("candidate_line_ratio", 0.0) >= 0.35
        or bool(signals.get("has_tracklist_structure"))
    )
    enough_by_absolute = (
        total >= MIN_SONG_COUNT
        and complete >= MIN_COMPLETE_SONG_COUNT
        and average >= MIN_COMPLETENESS_RATIO
    )
    pattern_valid = total >= 2 and complete >= 1 and strong_pattern
    success = bool(enough_by_absolute or pattern_valid)
    is_partial_but_valid = bool(pattern_valid and not enough_by_absolute)

    failure_reason = ""
    validity_reason = "absolute_threshold_met" if enough_by_absolute else ""
    if is_partial_but_valid:
        if signals.get("timestamp_count", 0) >= 2:
            validity_reason = "timestamp_pattern_detected"
        elif signals.get("pattern_count", 0) >= 2:
            validity_reason = "artist_title_delimiter_pattern_detected"
        elif signals.get("candidate_line_ratio", 0.0) >= 0.35:
            validity_reason = "candidate_line_ratio_detected"
        else:
            validity_reason = "tracklist_structure_detected"

    if not success:
        if len((source_text or "").strip()) < 20:
            failure_reason = "too_short"
        elif signals.get("timestamp_count", 0) == 0 and total == 0:
            failure_reason = "no_timestamps"
        elif total > 0 and total < MIN_SONG_COUNT and not strong_pattern:
            failure_reason = "too_few_songs_without_pattern"
        elif total > 0 and average < MIN_COMPLETENESS_RATIO:
            failure_reason = "low_completeness"
        elif signals.get("pattern_count", 0) == 0 and not strong_pattern:
            failure_reason = "no_pattern"
        elif total < MIN_SONG_COUNT:
            failure_reason = "too_few_songs"
        else:
            failure_reason = "no_pattern"

    return {
        "success": success,
        "is_partial_but_valid": is_partial_but_valid,
        "validity_reason": validity_reason,
        "failure_reason": failure_reason,
        "song_count": total,
        "complete_song_count": complete,
        "avg_completeness": round(average, 3),
    }
