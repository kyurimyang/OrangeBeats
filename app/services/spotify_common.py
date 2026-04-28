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
    "더보이즈": "THE BOYZ",
    "라이즈": "RIIZE",
    "트레저": "TREASURE",
    "세븐틴": "SEVENTEEN",
    "엔시티": "NCT",
    "투바투": "TOMORROW X TOGETHER",
    "TXT": "TOMORROW X TOGETHER",
    "투모로우바이투게더": "TOMORROW X TOGETHER",
}

ARTIST_ALIAS_MAP.update(CORE_ARTIST_ALIAS_MAP)
ARTIST_ALIAS_MAP.update({
    "\ub808\ub4dc\ubca8\ubcb3": ["Red Velvet", "REDVELVET"],
    "\ud2b8\uc640\uc774\uc2a4": ["TWICE"],
    "\uc18c\ub140\uc2dc\ub300": ["Girls' Generation", "Girls Generation", "SNSD"],
    "\uc6d0\ub354\uac78\uc2a4": ["Wonder Girls"],
    "\ub808\uc778\ubcf4\uc6b0": ["RAINBOW", "Rainbow"],
    "\ube44\uc2a4\ud2b8": ["BEAST"],
    "\uc778\ud53c\ub2c8\ud2b8": ["INFINITE"],
    "\uc0e4\uc774\ub2c8": ["SHINee"],
    "\uc5d4\ud558\uc774\ud508": ["ENHYPEN"],
    "\ub354\ubcf4\uc774\uc988": ["THE BOYZ"],
    "\ub77c\uc774\uc988": ["RIIZE"],
    "\ud2b8\ub808\uc800": ["TREASURE"],
    "\uc138\ube10\ud2f4": ["SEVENTEEN"],
    "\uc5d4\uc2dc\ud2f0 \ub4dc\ub9bc": ["NCT DREAM"],
    "\uc5d4\uc2dc\ud2f0": ["NCT"],
    "\ud22c\ubc14\ud22c": ["TOMORROW X TOGETHER"],
    "\ud22c\ubaa8\ub85c\uc6b0\ubc14\uc774\ud22c\uac8c\ub354": ["TOMORROW X TOGETHER"],
    "f(x)": ["F(x)", "f\uff08x\uff09"],
    "(G)I-DLE": ["GIDLE", "(G)I-DLE", "I-DLE"],
})
TITLE_ALIAS_MAP = dict(CORE_TITLE_ALIAS_MAP)

SUSPICIOUS_KEYWORDS = {
    'karaoke', 'cover', 'tribute', 'inst', 'instrumental', 'mr', 'live', 'concert',
    'remix', 'sped up', 'slowed', '8d', 'nightcore'
}


BRACKET_REGEX = re.compile(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}')
PARENTHETICAL_REGEX = re.compile(r'[\(\[\{]([^\)\]\}]{1,12})[\)\]\}]')
NON_WORD_REGEX = re.compile(r'[^\w가-힣\s]')
MULTISPACE_REGEX = re.compile(r'\s+')
BRACKET_CONTENT_REGEX = re.compile(r'[\(\[\{]([^\)\]\}]+)[\)\]\}]')
TRAILING_ELLIPSIS_REGEX = re.compile(r'(?:\.\.\.|…)+$')
TRAILING_PERIOD_REGEX = re.compile(r'\.+$')
TITLE_SYMBOL_RELAX_REGEX = re.compile(r"[!\"'`~@#$%^&*_+=]+")
MIXED_LANGUAGE_SPLIT_REGEX = re.compile(
    r"^([\uAC00-\uD7A3][\uAC00-\uD7A3\s]+?)\s+([A-Za-z][A-Za-z\s'!?.,]+)$"
)


def _normalize_text(value: str) -> str:
    value = (value or '').lower().strip()
    value = value.replace('&', ' and ')
    value = BRACKET_REGEX.sub(' ', value)
    value = re.sub(r'[^\w\uAC00-\uD7A3\s]', ' ', value)
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip()


def _normalize_parentheses(value: str) -> str:
    return (
        str(value or '')
        .replace('\uff08', '(')
        .replace('\uff09', ')')
        .replace('\uff3b', '[')
        .replace('\uff3d', ']')
        .replace('\uff5b', '{')
        .replace('\uff5d', '}')
    )


def _should_preserve_parenthetical_identifier(value: str, match: re.Match) -> bool:
    content = (match.group(1) or '').strip()
    if not content or re.search(r'\s', content):
        return False
    if not re.fullmatch(r'[A-Za-z0-9]+', content):
        return False

    start, end = match.span()
    prev_char = value[start - 1] if start > 0 else ''
    next_char = value[end] if end < len(value) else ''
    attached_to_identifier = bool(
        re.match(r'[A-Za-z0-9]', prev_char) or re.match(r'[A-Za-z0-9]', next_char)
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
    token_key = re.sub(r'[^A-Za-z0-9]', '', token)
    return 2 <= len(token_key) <= 24 and bool(re.search(r'[A-Za-z]', token_key))


def _strip_artist_bracketed_metadata(value: str) -> str:
    value = _normalize_parentheses(value)

    def replace(match: re.Match) -> str:
        if _should_preserve_parenthetical_identifier(value, match):
            return match.group(0)
        return ' '

    return PARENTHETICAL_REGEX.sub(replace, value)


def _normalize_artist_key(value: str) -> str:
    value = _strip_artist_bracketed_metadata(value)
    value = value.lower().replace('&', ' and ')
    value = re.sub(r'[^\w\uAC00-\uD7A3]', ' ', value)
    value = MULTISPACE_REGEX.sub('', value)
    return value.strip()


def _normalize_cache_text(value: str) -> str:
    return _normalize_text(value).replace(' ', '')


def _has_korean(value: str) -> bool:
    return bool(re.search(r'[\uAC00-\uD7A3]', value or ''))


def _canonicalize_alias_value(value: str, alias_map: Dict[str, List[str]]) -> str:
    cleaned = (value or '').strip()
    normalized = _normalize_artist_key(cleaned) if alias_map is ARTIST_ALIAS_MAP else _normalize_text(cleaned)
    for source, aliases in alias_map.items():
        alias_values = aliases if isinstance(aliases, list) else [aliases]
        if alias_map is ARTIST_ALIAS_MAP:
            normalized_group = {_normalize_artist_key(source), *(_normalize_artist_key(alias) for alias in alias_values)}
        else:
            normalized_group = {_normalize_text(source), *(_normalize_text(alias) for alias in alias_values)}
        if normalized in normalized_group:
            return source
    return cleaned


def resolve_artist_alias(artist: str) -> str:
    cleaned = _clean_artist_name_for_search(artist)
    normalized = _normalize_artist_key(cleaned)
    if not normalized:
        return cleaned

    for source, aliases in ARTIST_ALIAS_MAP.items():
        alias_values = aliases if isinstance(aliases, list) else [aliases]
        normalized_group = {_normalize_artist_key(source), *(_normalize_artist_key(alias) for alias in alias_values)}
        if normalized not in normalized_group:
            continue

        for alias in alias_values:
            candidate = (alias or '').strip()
            if candidate:
                return candidate
        return cleaned or source

    return cleaned


def build_match_cache_key(title: str, artist: str) -> Tuple[str, str]:
    canonical_artist = _canonicalize_alias_value(resolve_artist_alias(artist), ARTIST_ALIAS_MAP)
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
    variants = build_title_variants(title)
    for variant in variants[1:]:
        if variant:
            return variant
    return variants[0] if variants else ''


def _clean_artist_name_for_search(artist: str) -> str:
    value = _strip_artist_bracketed_metadata(artist or '')
    value = re.split(r'\s*(?:feat\.?|ft\.?|with|,|&| x )\s*', value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = MULTISPACE_REGEX.sub(' ', value)
    return value.strip(' -_/:|')


def build_title_variants(title: str) -> List[str]:
    original = MULTISPACE_REGEX.sub(' ', (title or '').strip())
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = MULTISPACE_REGEX.sub(' ', (candidate or '').strip())
        candidate = candidate.strip(' -_/|')
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(original)
    if not _is_short_title(original):
        add_variant(BRACKET_REGEX.sub(' ', original))

    for current in list(variants):
        add_variant(TRAILING_ELLIPSIS_REGEX.sub('', current).strip())
        add_variant(TRAILING_PERIOD_REGEX.sub('', current).strip())

    if not _is_short_title(original):
        add_variant(TITLE_SYMBOL_RELAX_REGEX.sub(' ', original))
        add_variant(_remove_title_noise(original))

    for current in list(variants):
        for alias_variant in _expand_alias_variants(current, TITLE_ALIAS_MAP):
            add_variant(_remove_title_noise(alias_variant))

    return (variants or [original])[:4]


def build_title_search_variants(title: str) -> List[str]:
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = MULTISPACE_REGEX.sub(' ', (candidate or '').strip())
        candidate = candidate.strip(' -_/|')
        if candidate and candidate not in variants:
            variants.append(candidate)

    for variant in _title_variants(title):
        add_variant(variant)

    return variants[:6]


def _expand_alias_variants(value: str, alias_map: Dict[str, List[str]]) -> List[str]:
    cleaned = (value or '').strip()
    normalized = _normalize_artist_key(cleaned) if alias_map is ARTIST_ALIAS_MAP else _normalize_text(cleaned)
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = (candidate or '').strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(cleaned)

    for source, aliases in alias_map.items():
        alias_values = aliases if isinstance(aliases, list) else [aliases]
        if alias_map is ARTIST_ALIAS_MAP:
            normalized_group = {_normalize_artist_key(source), *(_normalize_artist_key(alias) for alias in alias_values)}
        else:
            normalized_group = {_normalize_text(source), *(_normalize_text(alias) for alias in alias_values)}
        if normalized in normalized_group:
            add_variant(source)
            for alias in alias_values:
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


def build_artist_search_variants(artist: Optional[str]) -> List[str]:
    if not artist:
        return []

    cleaned = _clean_artist_name_for_search(artist)
    resolved = resolve_artist_alias(cleaned)
    variants: List[str] = []

    def add_variant(value: Optional[str]) -> None:
        value = (value or '').strip()
        if value and value not in variants:
            variants.append(value)

    add_variant(cleaned)
    add_variant(resolved)

    for variant in _expand_alias_variants(cleaned, ARTIST_ALIAS_MAP):
        add_variant(variant)
    for variant in _expand_alias_variants(resolved, ARTIST_ALIAS_MAP):
        add_variant(variant)

    split_parts = re.split(r'\s*(?:,|&| x | feat\.?|ft\.?)\s*', cleaned, flags=re.IGNORECASE)
    for part in split_parts:
        add_variant(part)

    return variants[:6]


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
    original = MULTISPACE_REGEX.sub(' ', (title or '').strip())
    variants = build_title_variants(original)

    for match in BRACKET_CONTENT_REGEX.findall(original):
        for variant in build_title_variants(match):
            if variant not in variants:
                variants.append(variant)

    if not _is_short_title(original):
        for delimiter in [' - ', ' – ', ' — ', ' : ', ' | ', ' / ']:
            if delimiter not in original:
                continue
            left, right = original.split(delimiter, 1)
            for variant in build_title_variants(left):
                if variant not in variants:
                    variants.append(variant)
            for variant in build_title_variants(right):
                if variant not in variants:
                    variants.append(variant)

    return variants or [original]


def _normalized_title_compare_key(value: str) -> str:
    value = _normalize_text(BRACKET_REGEX.sub(' ', value or ''))
    return re.sub(r'[^\w\uAC00-\uD7A3]', '', value)


def _candidate_title_compare_variants(candidate_title: str) -> List[str]:
    original = MULTISPACE_REGEX.sub(' ', (candidate_title or '').strip())
    variants: List[str] = []

    def add_variant(candidate: str) -> None:
        candidate = MULTISPACE_REGEX.sub(' ', (candidate or '').strip())
        candidate = candidate.strip(' -_/:|')
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(original)
    add_variant(BRACKET_REGEX.sub(' ', original))

    for match in BRACKET_CONTENT_REGEX.findall(original):
        add_variant(match)
        add_variant(TRAILING_PERIOD_REGEX.sub('', match).strip())

    for delimiter in [' - ', ' – ', ' — ', ' : ', ' | ', ' / ']:
        if delimiter not in original:
            continue
        left, right = original.split(delimiter, 1)
        add_variant(left)
        add_variant(right)

    mixed_match = MIXED_LANGUAGE_SPLIT_REGEX.match(original)
    if mixed_match:
        add_variant(mixed_match.group(1))
        add_variant(mixed_match.group(2))

    add_variant(_remove_title_noise(original))
    add_variant(TITLE_SYMBOL_RELAX_REGEX.sub(' ', original))

    return (variants or [original])[:8]


def _best_title_similarity(input_variants: List[str], candidate_title: str) -> Tuple[float, Dict[str, Any]]:
    candidate_variants = _candidate_title_compare_variants(candidate_title)
    best_score = 0.0
    best_input = ''
    best_candidate = ''

    for input_variant in input_variants:
        for candidate_variant in candidate_variants:
            score = _string_similarity(input_variant, candidate_variant)
            if score > best_score:
                best_score = score
                best_input = input_variant
                best_candidate = candidate_variant

    normalized_input = _normalized_title_compare_key(best_input or (input_variants[0] if input_variants else ''))
    normalized_candidates = [_normalized_title_compare_key(variant) for variant in candidate_variants]
    exact_normalized_match = bool(normalized_input and normalized_input in normalized_candidates)
    reason = "exact_or_normalized_title_variant" if exact_normalized_match else "best_title_variant_similarity"

    return round(best_score, 4), {
        "title_variant_matched": bool(best_candidate and (best_score >= 0.85 or exact_normalized_match)),
        "matched_title_variant": best_candidate,
        "normalized_input_title": normalized_input,
        "normalized_candidate_variants": normalized_candidates[:8],
        "title_match_reason": reason,
    }


def _is_short_or_generic_title(title: str) -> bool:
    tokens = _tokenize_text(title)
    generic = {'home', 'hello', 'run', 'you', 'night', 'love', 'day', 'dream', 'stay'}
    return len(tokens) <= 2 or any(token in generic for token in tokens)


def _string_similarity(a: str, b: str) -> float:
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    a_compact = _normalize_cache_text(a)
    b_compact = _normalize_cache_text(b)
    if len(a_compact) <= 2 or len(b_compact) <= 2:
        if a_compact == b_compact:
            return 1.0
        if a_compact and b_compact and (a_compact in b_compact or b_compact in a_compact):
            return 0.95
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92
    overlap = _token_overlap_ratio(a_norm, b_norm)
    if overlap > 0:
        return overlap
    return 0.0


def _artist_alias_match(input_artist: str, candidate_artists: List[str]) -> Tuple[bool, str]:
    input_cleaned = _clean_artist_name_for_search(input_artist)
    if not input_cleaned or not candidate_artists:
        return False, ''

    input_variants = _expand_alias_variants(input_cleaned, ARTIST_ALIAS_MAP)
    input_keys = {_normalize_artist_key(variant) for variant in input_variants if variant}
    input_keys.discard('')

    for candidate in candidate_artists:
        candidate_cleaned = _clean_artist_name_for_search(candidate)
        candidate_variants = _expand_alias_variants(candidate_cleaned, ARTIST_ALIAS_MAP)
        for variant in candidate_variants:
            if _normalize_artist_key(variant) in input_keys:
                return True, candidate_cleaned or variant

    return False, ''


def _artist_match_score(input_artist: str, candidate_artists: List[str]) -> float:
    if not input_artist or not candidate_artists:
        return 0.0

    alias_matched, _ = _artist_alias_match(input_artist, candidate_artists)
    if alias_matched:
        return 1.0

    normalized_input = resolve_artist_alias(input_artist)
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


def compute_match_score(input_title: str, input_artist: str, track: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    track_name = track.get('name', '')
    track_artists = [a.get('name', '') for a in track.get('artists', [])]

    clean_input_artist = _clean_artist_name_for_search(input_artist)
    input_title_variants = _title_variants(input_title)
    title_score, title_match_detail = _best_title_similarity(input_title_variants, track_name)
    artist_alias_matched, matched_alias = _artist_alias_match(clean_input_artist, track_artists)
    artist_score = 1.0 if artist_alias_matched else _artist_match_score(clean_input_artist, track_artists)
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
        'artist_alias_matched': artist_alias_matched,
        'matched_alias': matched_alias,
        **title_match_detail,
        'penalty': round(penalty, 4),
        'popularity_bonus': round(popularity_bonus, 4),
        'artist_mismatch_penalty': round(artist_mismatch_penalty, 4),
    }
