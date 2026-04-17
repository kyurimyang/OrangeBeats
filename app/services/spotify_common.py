import re
from typing import Any, Dict, List, Optional, Tuple

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
}

SUSPICIOUS_KEYWORDS = {
    'karaoke', 'cover', 'tribute', 'inst', 'instrumental', 'mr', 'live', 'concert',
    'remix', 'sped up', 'slowed', '8d', 'nightcore'
}


BRACKET_REGEX = re.compile(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}')
NON_WORD_REGEX = re.compile(r'[^\w가-힣\s]')
MULTISPACE_REGEX = re.compile(r'\s+')


def _normalize_text(value: str) -> str:
    value = (value or '').lower().strip()
    value = value.replace('&', ' and ')
    value = BRACKET_REGEX.sub(' ', value)
    value = NON_WORD_REGEX.sub(' ', value)
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip()


def _remove_title_noise(value: str) -> str:
    value = BRACKET_REGEX.sub(' ', value or '')
    value = re.sub(r'\bfeat\.?\b.*$', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'\bft\.?\b.*$', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'\bwith\b.*$', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'\b(prod|produced)\.?\b.*$', ' ', value, flags=re.IGNORECASE)
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip()


def _clean_track_title_for_search(title: str) -> str:
    return _remove_title_noise(title)


def _artist_variants(artist: Optional[str]) -> List[Optional[str]]:
    if not artist:
        return [None]

    cleaned = artist.strip()
    variants: List[Optional[str]] = []

    def add_variant(value: Optional[str]) -> None:
        value = (value or '').strip()
        if value and value not in variants:
            variants.append(value)

    add_variant(cleaned)

    split_parts = re.split(r'\s*(?:,|&| x | feat\.?|ft\.?)\s*', cleaned, flags=re.IGNORECASE)
    for part in split_parts:
        add_variant(part)

    normalized_cleaned = _normalize_text(cleaned)
    for source, aliases in ARTIST_ALIAS_MAP.items():
        source_norm = _normalize_text(source)
        alias_norms = [_normalize_text(x) for x in aliases]
        if normalized_cleaned == source_norm or normalized_cleaned in alias_norms:
            add_variant(source)
            for alias in aliases:
                add_variant(alias)

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
    base = (title or '').strip()
    variants: List[str] = []
    for candidate in [base, _remove_title_noise(base)]:
        candidate = MULTISPACE_REGEX.sub(' ', candidate).strip(' -_/')
        if candidate and candidate not in variants:
            variants.append(candidate)
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
    return _token_overlap_ratio(a_norm, b_norm)


def _artist_match_score(input_artist: str, candidate_artists: List[str]) -> float:
    if not input_artist or not candidate_artists:
        return 0.0

    input_variants = _artist_variants(input_artist)
    candidate_joined = ' , '.join(candidate_artists)
    best = 0.0
    for variant in input_variants:
        best = max(best, _string_similarity(variant or '', candidate_joined))
        for cand in candidate_artists:
            best = max(best, _string_similarity(variant or '', cand))
    return round(best, 4)


def _suspicious_penalty(name: str, artists: List[str]) -> float:
    haystack = _normalize_text(f"{name} {' '.join(artists)}")
    penalty = 0.0
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in haystack:
            penalty += 0.08
    return min(penalty, 0.24)


def compute_match_score(input_title: str, input_artist: str, track: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    track_name = track.get('name', '')
    track_artists = [a.get('name', '') for a in track.get('artists', [])]

    title_score = _string_similarity(input_title, track_name)
    artist_score = _artist_match_score(input_artist, track_artists)
    popularity_bonus = min((track.get('popularity') or 0) / 1000, 0.03)
    penalty = _suspicious_penalty(track_name, track_artists)

    if input_artist:
        final = (title_score * 0.62) + (artist_score * 0.33) + popularity_bonus - penalty
    else:
        final = (title_score * 0.9) + popularity_bonus - penalty

    final = max(0.0, min(round(final, 4), 1.0))
    return final, {
        'title_score': round(title_score, 4),
        'artist_score': round(artist_score, 4),
        'penalty': round(penalty, 4),
        'popularity_bonus': round(popularity_bonus, 4),
    }
