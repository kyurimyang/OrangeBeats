import re
from typing import Any, Dict, List, Optional, Tuple

from app.constants.pipeline_params import CORE_ARTIST_ALIAS_MAP, CORE_TITLE_ALIAS_MAP, MATCH_NOISE_KEYWORDS

COMMON_TITLE_STOPWORDS = {
    'official', 'audio', 'mv', 'm v', 'music', 'video', 'lyrics', 'lyric',
    'live', 'ver', 'version', 'remaster', 'remastered', 'inst', 'instrumental',
    'cover', 'karaoke', 'sped', 'up', 'slowed'
}

ARTIST_ALIAS_MAP = {
    '클래지콰이': ['clazziquai', 'clazziquai project'],
    '롤러코스터': ['roller coaster', 'rollercoaster'],
    '조원선': ['joe wonsun'],
    '윤상': ['yoon sang'],
    '악뮤': ['akmu', 'akdong musician'],
    '소녀시대': ["girls' generation", 'girls generation', 'snsd'],
    '아이유': ['iu'],
    '백예린': ['yerin baek'],
    '태연': ['taeyeon'],
    '방탄소년단': ['bts'],
    "릴러말즈": "Leellamarz",
    "페노메코": "PENOMECO",
    "블락비": "Block B",
    "엔하이픈": "ENHYPEN",
    "백현": "BAEKHYUN",
    "아이콘": "iKON",
    "지드래곤": "G-DRAGON",
    "방탄소년단": "BTS",
    "엑소": "EXO",
    "지코": "ZICO",
    "딘": "DEAN",
    "크러쉬": "Crush",
    "헤이즈": "Heize",
    "엔시티": "NCT",
    "엔시티 127": "NCT 127",
    "엔시티 드림": "NCT DREAM",
    "백예린": "Yerin Baek",
    "원슈타인": "Wonstein",
    "MC몽": "MC Mong",
}

ARTIST_ALIAS_MAP.update(CORE_ARTIST_ALIAS_MAP)
TITLE_ALIAS_MAP = dict(CORE_TITLE_ALIAS_MAP)

SUSPICIOUS_KEYWORDS = {
    'karaoke', 'cover', 'tribute', 'inst', 'instrumental', 'mr', 'live', 'concert',
    'remix', 'sped up', 'slowed', '8d', 'nightcore'
}


BRACKET_REGEX = re.compile(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}')
NON_WORD_REGEX = re.compile(r'[^\w가-힣\s]')
MULTISPACE_REGEX = re.compile(r'\s+')
BRACKET_CONTENT_REGEX = re.compile(r'[\(\[\{]([^\)\]\}]+)[\)\]\}]')


def _normalize_text(value: str) -> str:
    value = (value or '').lower().strip()
    value = value.replace('&', ' and ')
    value = BRACKET_REGEX.sub(' ', value)
    value = re.sub(r'[^\w\uAC00-\uD7A3\s]', ' ', value)
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip()


def _normalize_cache_text(value: str) -> str:
    return _normalize_text(value).replace(' ', '')


def _has_korean(value: str) -> bool:
    return bool(re.search(r'[\uAC00-\uD7A3]', value or ''))


def _canonicalize_alias_value(value: str, alias_map: Dict[str, List[str]]) -> str:
    cleaned = (value or '').strip()
    normalized = _normalize_text(cleaned)
    for source, aliases in alias_map.items():
        normalized_group = {_normalize_text(source), *(_normalize_text(alias) for alias in aliases)}
        if normalized in normalized_group:
            return source
    return cleaned


def build_match_cache_key(title: str, artist: str) -> Tuple[str, str]:
    canonical_artist = _canonicalize_alias_value(_clean_artist_name_for_search(artist), ARTIST_ALIAS_MAP)
    canonical_title = _canonicalize_alias_value(_clean_track_title_for_search(title), TITLE_ALIAS_MAP)
    return (
        _normalize_cache_text(canonical_artist),
        _normalize_cache_text(canonical_title),
    )


def _is_short_title(value: str) -> bool:
    return len(_normalize_cache_text(value)) <= 2


def _split_translation_suffix(value: str) -> str:
    if _is_short_title(value):
        return value

    for delimiter in [' - ', ' – ', ' — ', ' : ', ' | ', ' / ']:
        if delimiter not in value:
            continue
        head, tail = value.split(delimiter, 1)
        head = head.strip()
        tail = tail.strip()
        if not head or not tail:
            continue

        tail_norm = _normalize_text(tail)
        looks_like_translation = _has_korean(head) and not _has_korean(tail) and bool(re.search(r'[A-Za-z]', tail))
        looks_like_noise = any(token in tail_norm for token in MATCH_NOISE_KEYWORDS)
        if looks_like_translation or looks_like_noise:
            return head

    return value


def _remove_title_noise(value: str) -> str:
    original = (value or '').strip()
    value = _split_translation_suffix(original)
    value = BRACKET_REGEX.sub(' ', value)
    remove_patterns = [
        r'\bfeat\.?\b.*$',
        r'\bft\.?\b.*$',
        r'\bwith\b.*$',
        r'\b(prod|produced)\.?\b.*$',
        r'\bremix\b.*$',
        r'\bversion\b.*$',
        r'\bver\.?\b.*$',
        r'\bremaster(?:ed)?\b.*$',
        r'\bofficial(?:\s+audio|\s+video)?\b.*$',
        r'\blyrics?\b.*$',
        r'\bmv\b.*$',
        r'\bost\b.*$',
    ]
    for pattern in remove_patterns:
        value = re.sub(pattern, ' ', value, flags=re.IGNORECASE)
    value = MULTISPACE_REGEX.sub(' ', value)
    value = value.strip(' -_/:|')
    return value or original


def _clean_track_title_for_search(title: str) -> str:
    return _remove_title_noise(title)


def _clean_artist_name_for_search(artist: str) -> str:
    value = BRACKET_REGEX.sub(' ', artist or '')
    value = re.split(r'\s*(?:feat\.?|ft\.?|with|,|&| x )\s*', value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip(' -_/:|')


def _expand_alias_variants(value: str, alias_map: Dict[str, List[str]]) -> List[str]:
    cleaned = (value or '').strip()
    normalized = _normalize_text(cleaned)
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = (candidate or '').strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(cleaned)

    for source, aliases in alias_map.items():
        normalized_group = {_normalize_text(source), *(_normalize_text(alias) for alias in aliases)}
        if normalized in normalized_group:
            add_variant(source)
            for alias in aliases:
                add_variant(alias)

    return variants


def _artist_variants(artist: Optional[str]) -> List[Optional[str]]:
    if not artist:
        return [None]

    cleaned = _clean_artist_name_for_search(artist)
    variants: List[Optional[str]] = []

    def add_variant(value: Optional[str]) -> None:
        value = (value or '').strip()
        if value and value not in variants:
            variants.append(value)

    for variant in _expand_alias_variants(cleaned, ARTIST_ALIAS_MAP):
        add_variant(variant)

    split_parts = re.split(r'\s*(?:,|&| x | feat\.?|ft\.?)\s*', cleaned, flags=re.IGNORECASE)
    for part in split_parts:
        add_variant(part)

    return variants or [cleaned]


def _tokenize_text(value: str) -> List[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split() if token and token not in COMMON_TITLE_STOPWORDS]


def _token_overlap_ratio(a: str, b: str) -> float:
    a_tokens = set(_tokenize_text(a))
    b_tokens = set(_tokenize_text(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return round(len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens)), 4)


def _is_suspicious_song(song: Dict[str, Any]) -> bool:
    title = (song.get('title') or '').strip()
    artist = (song.get('artist') or '').strip()
    if not title:
        return True
    if artist and _normalize_text(title) == _normalize_text(artist):
        return True
    return False


def _title_variants(title: str) -> List[str]:
    original = (title or '').strip()
    base = _clean_track_title_for_search(original)
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = MULTISPACE_REGEX.sub(' ', candidate).strip(' -_/')
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(base)

    for match in BRACKET_CONTENT_REGEX.findall(original):
        add_variant(_clean_track_title_for_search(match))

    if not _is_short_title(base):
        for delimiter in [' - ', ' – ', ' — ', ' : ', ' | ', ' / ']:
            if delimiter not in original:
                continue
            left, right = original.split(delimiter, 1)
            left = _clean_track_title_for_search(left)
            right = _clean_track_title_for_search(right)
            if left and right:
                add_variant(left)
                add_variant(right)

    for candidate in list(variants):
        for alias_variant in _expand_alias_variants(candidate, TITLE_ALIAS_MAP):
            add_variant(_clean_track_title_for_search(alias_variant))

    return variants or [base]


def _is_short_or_generic_title(title: str) -> bool:
    tokens = _tokenize_text(title)
    generic = {'home', 'hello', 'run', 'you', 'night', 'love', 'day', 'dream', 'stay'}
    return len(tokens) <= 2 or any(token in generic for token in tokens)


def _string_similarity(a: str, b: str) -> float:
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92
    overlap = _token_overlap_ratio(a_norm, b_norm)
    if overlap > 0:
        return overlap
    return 0.0


def _artist_match_score(input_artist: str, candidate_artists: List[str]) -> float:
    if not input_artist or not candidate_artists:
        return 0.0

    normalized_input = _clean_artist_name_for_search(input_artist)
    input_variants = _artist_variants(normalized_input)
    candidate_cleaned = [_clean_artist_name_for_search(name) for name in candidate_artists if name]
    candidate_joined = ' , '.join(candidate_cleaned)
    best = 0.0
    for variant in input_variants:
        best = max(best, _string_similarity(variant or '', candidate_joined))
        for cand in candidate_cleaned:
            best = max(best, _string_similarity(variant or '', cand))
    return round(best, 4)


def _suspicious_penalty(name: str, artists: List[str]) -> float:
    haystack = _normalize_text(f"{name} {' '.join(artists)}")
    penalty = 0.0
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in haystack:
            penalty += 0.08
    for keyword in MATCH_NOISE_KEYWORDS:
        if keyword in haystack:
            penalty += 0.03
    return min(penalty, 0.24)


def compute_match_score(input_title: str, input_artist: str, track: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    track_name = track.get('name', '')
    track_artists = [a.get('name', '') for a in track.get('artists', [])]

    clean_input_artist = _clean_artist_name_for_search(input_artist)
    input_title_variants = _title_variants(input_title)
    track_title_variants = _title_variants(track_name)

    title_score = max(
        (
            _string_similarity(input_variant, track_variant)
            for input_variant in input_title_variants
            for track_variant in track_title_variants
        ),
        default=0.0,
    )
    artist_score = _artist_match_score(clean_input_artist, track_artists)
    popularity_bonus = min((track.get('popularity') or 0) / 1000, 0.03)
    penalty = _suspicious_penalty(track_name, track_artists)
    artist_mismatch_penalty = 0.0

    if clean_input_artist:
        if artist_score < 0.15:
            artist_mismatch_penalty = 0.35
        elif artist_score < 0.35:
            artist_mismatch_penalty = 0.18

    if clean_input_artist:
        final = (
            (title_score * 0.58)
            + (artist_score * 0.37)
            + popularity_bonus
            - penalty
            - artist_mismatch_penalty
        )
    else:
        final = (title_score * 0.9) + popularity_bonus - penalty

    if clean_input_artist and title_score >= 0.85 and artist_score < 0.2:
        final = min(final, 0.69)

    final = max(0.0, min(round(final, 4), 1.0))
    return final, {
        'title_score': round(title_score, 4),
        'artist_score': round(artist_score, 4),
        'penalty': round(penalty, 4),
        'popularity_bonus': round(popularity_bonus, 4),
        'artist_mismatch_penalty': round(artist_mismatch_penalty, 4),
    }
