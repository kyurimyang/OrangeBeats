import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    ARTIST_ALIAS_MAP,
    TITLE_ALIAS_MAP,
    build_artist_search_variants,
    build_match_cache_key,
    build_title_search_variants,
    compute_match_score,
    _clean_artist_name_for_search,
    _clean_track_title_for_search,
    _expand_alias_variants,
    _has_english,
    _has_korean,
    _remove_title_noise,
    _possible_artist_romanization_match,
    resolve_artist_alias,
    _string_similarity,
    _token_overlap_ratio,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
_MATCH_DEBUG: Dict[Tuple[str, str], Dict[str, Any]] = {}

EARLY_RETURN_SCORE = 0.90
DIRECT_ACCEPT_SCORE = 0.80
MIN_ACCEPT_SCORE = 0.80
MIN_TITLE_SCORE = 0.65
MIN_ARTIST_SCORE = 0.45
EXACT_ARTIST_SCORE = 0.999
EXACT_ARTIST_MIN_TITLE_SCORE = 0.50
MAX_CACHE_SIZE = 300
SEARCH_LIMIT = 3
MAX_QUERY_COUNT = 2
SWAP_GUARD_MARGIN = 0.05

# Candidate classification thresholds. These do not trigger extra Spotify requests.
ARTIST_ALIAS_CANDIDATE_TITLE_SCORE = 0.90
TITLE_ALIAS_CANDIDATE_ARTIST_SCORE = 0.95
TITLE_MISMATCH_ARTIST_SCORE = 0.85
TITLE_MISMATCH_MAX_TITLE_SCORE = 0.45
PARTIAL_CONFIDENCE_SCORE = 0.65
PROBABLE_MATCH_SCORE = 0.70
REVIEW_NEEDED_SCORE = 0.55

ACCEPTABLE_VERSION_KEYWORDS = {
    "live",
    "remaster",
    "remastered",
    "acoustic",
    "duet",
    "explicit",
    "radio edit",
    "edit",
}
NON_ORIGINAL_KEYWORDS = {
    "mr",
    "karaoke",
    "noraebang",
    "노래방",
    "금영",
    "ky",
    "tj",
    "cover",
    "piano cover",
    "remix",
    "prod by",
    "produced by",
    "performance",
    "instrumental",
    "inst",
    "tribute",
    "lullaby",
    "nightcore",
}
QUERY_RELIABILITY_WEIGHT = {
    "high": 3,
    "medium": 2,
    "low": 1,
}
SHORT_TITLE_RISK_TOKENS = {
    "one",
    "love",
    "blue",
    "fatal",
    "rain",
    "home",
    "hello",
    "run",
    "stay",
    "dream",
    "you",
    "day",
}

REASON_MESSAGES = {
    "matched": "자동 매칭되었습니다.",
    "probable_match": "표기 차이 가능성이 있지만 자동 매칭되었습니다.",
    "review_needed": "확인이 필요한 후보입니다.",
    "invalid_candidate": "아티스트 별칭/로마자 근거가 없고 제목 유사도도 낮아 제외했습니다.",
    "title_matched_artist_alias_candidate": "제목은 일치하지만 가수명이 Spotify에서 다른 표기로 등록되어 확인이 필요합니다.",
    "artist_matched_title_mismatch": "가수는 일치하지만 제목이 다른 표기로 등록되어 확인이 필요합니다.",
    "artist_matched_title_alias_candidate": "가수는 일치하지만 제목이 다른 언어/표기로 등록된 후보일 수 있습니다.",
    "official_spotify_metadata_candidate": "Spotify API에서 영어/로마자 공식 메타데이터로 반환된 후보입니다. 아티스트 로마자 표기와 검색 순위를 기준으로 추가 후보로 판단했습니다.",
    "top_candidate_artist_romanization_title_mismatch": "검색 1위 후보이며 가수명 로마자 표기 차이 가능성이 있습니다.",
    "partial_match_needs_review": "일부 정보가 유사하지만 자동 확정하기에는 점수가 낮습니다.",
    "version_candidate": "Live/Remix/Instrumental 등 다른 버전일 가능성이 있어 확인이 필요합니다.",
    "no_search_result": "Spotify 검색 결과가 없습니다.",
    "artist_mismatch": "후보는 찾았지만 가수명이 일치하지 않습니다.",
    "title_mismatch": "후보는 찾았지만 제목 유사도가 낮습니다.",
    "weak_title_and_artist": "제목과 가수명이 모두 약하게 일치합니다.",
    "low_score": "후보는 찾았지만 전체 유사도가 낮습니다.",
    "non_original_audio": "노래방/커버/Instrumental 등 원곡이 아닌 음원일 가능성이 큽니다.",
    "artist_only_overconfidence": "가수는 비슷하지만 제목이 달라 자동 매칭하지 않았습니다.",
    "title_only_overconfidence": "제목은 비슷하지만 가수가 달라 자동 매칭하지 않았습니다.",
    "short_title_false_positive": "짧은 제목이라 부분 일치만으로는 확정하기 어렵습니다.",
}


def _candidate_to_result(
    track: Dict[str, Any],
    score: float,
    detail: Dict[str, float],
    *,
    search_title: str,
    search_artist: str,
    chosen_case: str,
) -> Dict[str, Any]:
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "name": track.get("name", ""),
        "artists": [artist.get("name", "") for artist in track.get("artists", [])],
        "album": (track.get("album") or {}).get("name", ""),
        "album_image": next(
            (
                image.get("url")
                for image in (track.get("album") or {}).get("images", [])
                if image.get("url")
            ),
            None,
        ),
        "duration_ms": track.get("duration_ms"),
        "popularity": int(track.get("popularity") or 0),
        "score": score,
        "score_detail": detail,
        "orientation": "title_artist" if chosen_case == "swapped" else "artist_title",
        "chosen_case": chosen_case,
        "llm_reranked": False,
        "llm_confidence": "",
        "llm_reason": "",
        "search_title": search_title,
        "search_artist": search_artist,
    }


def _candidate_score_log(candidate: Dict[str, Any]) -> str:
    detail = candidate.get("score_detail", {})
    score = float(candidate.get("score", 0.0))
    confidence = candidate.get("match_status") or _status_from_score(score)
    base_score = float(detail.get("base_score", detail.get("score_before_context", score)))
    return (
        f"input_api_added=false query_added=false "
        f"{candidate.get('artists', [])} - {candidate.get('name', '')} "
        f"base={base_score:.2f} "
        f"title={float(detail.get('title_score', 0.0)):.2f} "
        f"artist={float(detail.get('artist_score', 0.0)):.2f} "
        f"token={float(detail.get('token_score', 0.0)):.2f} "
        f"patterns={detail.get('pattern_tags', [])} "
        f"bonuses={detail.get('bonuses', dict())} "
        f"penalties={detail.get('penalties', dict())} "
        f"final={score:.2f} "
        f"confidence={confidence} "
        f"chosen_reason='{candidate.get('user_message', '')}' "
        f"rejected_reason='{candidate.get('unmatched_reason', '')}'"
    )


def _reason_message(reason: str) -> str:
    return REASON_MESSAGES.get(reason, reason or "확인 가능한 사유가 없습니다.")


def explain_match_reason(reason: str) -> str:
    return _reason_message(reason)


def _status_from_score(score: float) -> str:
    if score >= DIRECT_ACCEPT_SCORE:
        return "matched"
    if score >= PROBABLE_MATCH_SCORE:
        return "probable_match"
    if score >= REVIEW_NEEDED_SCORE:
        return "review_needed"
    return "unmatched"


def normalize_title(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", value)
    value = re.sub(r"[\u2010-\u2015:|/]+", " ", value)
    value = re.sub(r"[^\w\uAC00-\uD7A3\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_artist(value: str) -> str:
    value = normalize_title(value)
    value = re.sub(r"\b(feat|ft|featuring|with)\b.*$", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_title_variants(value: str) -> List[str]:
    normalized = normalize_title(value)
    compact = normalized.replace(" ", "")
    variants = [item for item in {normalized, compact} if item]
    return variants


def get_artist_aliases(value: str) -> List[str]:
    normalized = normalize_artist(value)
    compact = normalized.replace(" ", "")
    return [item for item in {normalized, compact} if item]


def _add_variant(variants: List[str], value: str) -> None:
    value = (value or "").strip()
    if value and value not in variants:
        variants.append(value)


def _variant_keys(value: str) -> set[str]:
    normalized = normalize_title(value)
    compact = normalized.replace(" ", "")
    return {item for item in {normalized, compact} if item}


def _split_artist_parts(value: str) -> List[str]:
    cleaned = _clean_artist_name_for_search(value or "") or (value or "")
    parts = re.split(r"\s*(?:,|&| x | and |feat\.?|ft\.?|featuring|with)\s*", cleaned, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part and part.strip()]


def _extract_title_core_and_features(value: str) -> Tuple[str, List[str], List[str]]:
    raw = (value or "").strip()
    normalized = raw.replace("\uff08", "(").replace("\uff09", ")")
    tags: List[str] = []
    featured: List[str] = []

    feature_match = re.search(r"[\(\[\{]?\s*(?:feat|ft|featuring)\.?\s+([^\)\]\}]+)", normalized, flags=re.IGNORECASE)
    if feature_match:
        tags.append("featured_artist_metadata")
        featured_text = re.split(
            r"\b(?:prod(?:uced)?\s+by|remix|instrumental|inst|live|remaster(?:ed)?)\b",
            feature_match.group(1),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        featured = _split_artist_parts(featured_text)

    core = re.split(
        r"[\(\[\{]?\s*(?:feat|ft|featuring)\.?\s+|\bprod(?:uced)?\s+by\b|\bremix\b|\binstrumental\b|\binst\b",
        normalized,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    core = core.strip(" -_/:|")
    return core or raw, featured, tags


def _build_title_compare_variants(value: str) -> List[str]:
    variants: List[str] = []
    core, _featured, _tags = _extract_title_core_and_features(value)
    seeds = [value, core, _remove_title_noise(value), _clean_track_title_for_search(value)]

    for seed in seeds:
        _add_variant(variants, seed)
        for alias in _expand_alias_variants(seed, TITLE_ALIAS_MAP):
            _add_variant(variants, alias)

    for current in list(variants):
        normalized = normalize_title(current)
        _add_variant(variants, normalized)
        _add_variant(variants, normalized.replace(" ", ""))

    return variants[:16]


def _build_artist_compare_variants(value: str | List[str]) -> List[str]:
    raw_values = value if isinstance(value, list) else [value]
    variants: List[str] = []

    for raw in raw_values:
        _add_variant(variants, raw or "")
        for part in _split_artist_parts(raw or ""):
            _add_variant(variants, part)
            _add_variant(variants, resolve_artist_alias(part))
            for alias in _expand_alias_variants(part, ARTIST_ALIAS_MAP):
                _add_variant(variants, alias)

    if len(raw_values) > 1:
        _add_variant(variants, " ".join(raw_values))

    for current in list(variants):
        normalized = normalize_artist(current)
        _add_variant(variants, normalized)
        _add_variant(variants, normalized.replace(" ", ""))

    return variants[:24]


def _best_variant_similarity(input_variants: List[str], candidate_variants: List[str]) -> Tuple[float, str, str, bool]:
    best_score = 0.0
    best_input = ""
    best_candidate = ""
    exact = False
    input_keys = set()
    for variant in input_variants:
        input_keys.update(_variant_keys(variant))

    for input_variant in input_variants:
        for candidate_variant in candidate_variants:
            score = _string_similarity(input_variant, candidate_variant)
            if score > best_score:
                best_score = score
                best_input = input_variant
                best_candidate = candidate_variant
            if _variant_keys(candidate_variant) & input_keys:
                exact = True
                best_score = max(best_score, 1.0)
                best_input = best_input or input_variant
                best_candidate = best_candidate or candidate_variant

    return round(best_score, 4), best_input, best_candidate, exact


def _enrich_variant_detail(
    *,
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    enriched = dict(detail)
    input_title_variants = _build_title_compare_variants(input_title)
    candidate_title_variants = _build_title_compare_variants(candidate_title)
    input_artist_variants = _build_artist_compare_variants(input_artist)
    candidate_artist_variants = _build_artist_compare_variants(candidate_artists)
    title_variant_score, title_input, title_candidate, title_exact = _best_variant_similarity(
        input_title_variants,
        candidate_title_variants,
    )
    artist_variant_score, artist_input, artist_candidate, artist_exact = _best_variant_similarity(
        input_artist_variants,
        candidate_artist_variants,
    )
    title_alias_matched = bool(enriched.get("title_alias_matched")) or title_exact
    artist_alias_matched = bool(enriched.get("artist_alias_matched")) or artist_exact
    romanization_matched = (
        (_has_korean(input_title) and any(_has_english(value) for value in candidate_title_variants) and title_variant_score >= 0.72)
        or (_has_korean(input_artist) and any(_has_english(value) for value in candidate_artist_variants) and artist_variant_score >= 0.72)
        or bool(artist_alias_matched and _has_korean(input_artist))
        or bool(title_alias_matched and _has_korean(input_title))
    )
    title_core, featured_artists, feature_tags = _extract_title_core_and_features(input_title)

    enriched.update({
        "normalized_input_title": normalize_title(title_core or input_title),
        "normalized_candidate_variants": [normalize_title(value) for value in candidate_title_variants[:10] if normalize_title(value)],
        "input_title_variants": input_title_variants[:10],
        "candidate_title_variants": candidate_title_variants[:12],
        "input_artist_variants": input_artist_variants[:12],
        "candidate_artist_variants": candidate_artist_variants[:12],
        "title_variant_score": max(float(enriched.get("title_score", 0.0)), title_variant_score),
        "artist_variant_score": max(float(enriched.get("artist_score", 0.0)), artist_variant_score),
        "title_alias_matched": title_alias_matched,
        "artist_alias_matched": artist_alias_matched,
        "romanization_matched": romanization_matched,
        "matched_title_variant": enriched.get("matched_title_variant") or title_candidate,
        "matched_artist_variant": artist_candidate,
        "matched_input_title_variant": title_input,
        "matched_input_artist_variant": artist_input,
        "featured_artist_variants": _build_artist_compare_variants(featured_artists) if featured_artists else [],
    })
    if feature_tags:
        existing_tags = list(enriched.get("variant_pattern_tags", []))
        enriched["variant_pattern_tags"] = sorted(set(existing_tags + feature_tags))
    return enriched


def calculate_base_score(input_title: str, input_artist: str, track: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    return compute_match_score(input_title, input_artist, track)


def _candidate_text(candidate_title: str, candidate_artists: List[str]) -> str:
    return normalize_title(f"{candidate_title} {' '.join(candidate_artists)}")


def _contains_keyword(haystack: str, keywords: set[str]) -> bool:
    normalized = normalize_title(haystack)
    return any(keyword in normalized for keyword in keywords)


def _token_count(value: str) -> int:
    return len([token for token in normalize_title(value).split() if token])


def _is_short_title_false_positive(input_title: str, candidate_title: str, title_score: float) -> bool:
    input_tokens = normalize_title(input_title).split()
    candidate_tokens = normalize_title(candidate_title).split()
    if not input_tokens or len(input_tokens) > 2:
        return False
    risky = len(input_tokens) == 1 and input_tokens[0] in SHORT_TITLE_RISK_TOKENS
    much_longer = len(candidate_tokens) >= len(input_tokens) + 3
    return title_score >= 0.70 and (risky or much_longer)


def classify_candidate_patterns(
    *,
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    detail: Dict[str, Any],
    base_score: float,
    api_rank: int,
) -> List[str]:
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    title_variant_score = float(detail.get("title_variant_score", title_score))
    artist_variant_score = float(detail.get("artist_variant_score", artist_score))
    version_penalty = float(detail.get("version_penalty", 0.0))
    haystack = _candidate_text(candidate_title, candidate_artists)
    tags: List[str] = []

    if title_variant_score >= 0.95 and (not input_artist or artist_variant_score >= 0.85):
        tags.append("exact_match_pattern")

    if (
        bool(detail.get("artist_alias_matched"))
        or bool(detail.get("title_alias_matched"))
        or bool(detail.get("title_variant_matched"))
        or bool(detail.get("romanization_matched"))
        or title_variant_score >= 0.90
        or artist_variant_score >= 0.90
    ):
        tags.append("notation_difference_pattern")

    if version_penalty > 0 or _contains_keyword(haystack, ACCEPTABLE_VERSION_KEYWORDS):
        tags.append("acceptable_version_pattern")

    if _contains_keyword(haystack, NON_ORIGINAL_KEYWORDS):
        tags.append("non_original_audio_pattern")

    if input_artist and artist_variant_score >= 0.85 and title_variant_score < 0.55:
        tags.append("artist_only_overconfidence_pattern")

    if input_artist and title_variant_score >= 0.85 and artist_variant_score < MIN_ARTIST_SCORE:
        tags.append("title_only_overconfidence_pattern")

    if _is_short_title_false_positive(input_title, candidate_title, title_variant_score):
        tags.append("short_title_false_positive_pattern")

    if title_variant_score < 0.40 and (not input_artist or artist_variant_score < 0.40):
        tags.append("weak_both_pattern")

    if api_rank == 0 and (title_variant_score >= 0.95 or artist_variant_score >= 0.95):
        tags.append("top_rank_one_side_exact_pattern")

    for tag in detail.get("variant_pattern_tags", []):
        if tag not in tags:
            tags.append(tag)

    return tags


def apply_pattern_adjustments(
    base_score: float,
    detail: Dict[str, Any],
    pattern_tags: List[str],
) -> Tuple[float, Dict[str, Any]]:
    adjusted = float(base_score)
    enriched = dict(detail)
    title_score = float(enriched.get("title_score", 0.0))
    artist_score = float(enriched.get("artist_score", 0.0))
    title_variant_score = float(enriched.get("title_variant_score", title_score))
    artist_variant_score = float(enriched.get("artist_variant_score", artist_score))
    bonuses: Dict[str, float] = {}
    penalties: Dict[str, float] = {}
    caps: Dict[str, float] = {}

    if "exact_match_pattern" in pattern_tags:
        bonuses["exact_match_pattern"] = 0.03
        adjusted += 0.03

    if "notation_difference_pattern" in pattern_tags:
        bonuses["notation_difference_pattern"] = 0.03
        adjusted += 0.03
        if title_variant_score >= 0.92 and artist_variant_score >= 0.70:
            floor = 0.80 if (title_variant_score >= 0.98 and artist_variant_score >= 0.85) else 0.72
            adjusted = max(adjusted, floor)
            bonuses["variant_pair_floor"] = round(max(0.0, floor - base_score), 4)
        if (
            title_variant_score >= 0.98
            and artist_variant_score < MIN_ARTIST_SCORE
            and (bool(enriched.get("artist_alias_matched")) or bool(enriched.get("romanization_matched")) or artist_variant_score >= 0.25)
        ):
            adjusted = max(adjusted, 0.78)
            bonuses["title_exact_artist_spelling_gap_floor"] = round(max(0.0, 0.78 - base_score), 4)
        if artist_variant_score >= 0.98 and title_variant_score < MIN_TITLE_SCORE:
            adjusted = max(adjusted, 0.72)
            bonuses["artist_exact_title_spelling_gap_floor"] = round(max(0.0, 0.72 - base_score), 4)

    if "top_rank_one_side_exact_pattern" in pattern_tags:
        bonuses["top_rank_one_side_exact_bonus"] = 0.10
        adjusted += 0.10

    if "acceptable_version_pattern" in pattern_tags:
        penalty = min(float(enriched.get("version_penalty", 0.04)) or 0.04, 0.08)
        penalties["acceptable_version_pattern"] = penalty
        adjusted -= penalty

    if "non_original_audio_pattern" in pattern_tags:
        penalties["non_original_audio_pattern"] = 0.35
        adjusted -= 0.35
        caps["non_original_audio_pattern"] = 0.49

    one_side_exact_spelling_gap = (
        "notation_difference_pattern" in pattern_tags
        and "top_rank_one_side_exact_pattern" in pattern_tags
        and (title_variant_score >= 0.98 or artist_variant_score >= 0.98)
        and (
            bool(enriched.get("artist_alias_matched"))
            or bool(enriched.get("title_alias_matched") and artist_variant_score >= MIN_ARTIST_SCORE)
            or bool(enriched.get("romanization_matched"))
        )
    )

    if "artist_only_overconfidence_pattern" in pattern_tags and not one_side_exact_spelling_gap:
        caps["artist_only_overconfidence_pattern"] = 0.69

    if "title_only_overconfidence_pattern" in pattern_tags and not one_side_exact_spelling_gap:
        penalties["title_only_overconfidence_pattern"] = 0.12
        adjusted -= 0.12
        if bool(enriched.get("artist_alias_matched")) or bool(enriched.get("romanization_matched")):
            caps["title_only_overconfidence_pattern"] = 0.78
        else:
            caps["title_only_overconfidence_pattern"] = 0.69

    if "short_title_false_positive_pattern" in pattern_tags:
        penalties["short_title_false_positive_pattern"] = 0.20
        adjusted -= 0.20
        caps["short_title_false_positive_pattern"] = 0.62

    if "weak_both_pattern" in pattern_tags:
        caps["weak_both_pattern"] = 0.49

    if caps:
        adjusted = min(adjusted, min(caps.values()))

    final = max(0.0, min(round(adjusted, 4), 1.0))
    enriched["base_score"] = round(float(base_score), 4)
    enriched["pattern_tags"] = pattern_tags
    enriched["bonuses"] = bonuses
    enriched["penalties"] = penalties
    enriched["score_caps"] = caps
    enriched["final_score"] = final
    enriched["api_call_added"] = False
    enriched["query_added"] = False
    return final, enriched


def _query_contains_title_and_artist(query_used: str, input_title: str, input_artist: str) -> bool:
    query_norm = normalize_title(query_used)
    title_norm = normalize_title(input_title)
    artist_parts = _split_artist_parts(input_artist)
    artist_supported = not input_artist or any(normalize_title(part) and normalize_title(part) in query_norm for part in artist_parts)
    return bool(title_norm and title_norm in query_norm and artist_supported)


def _query_reliability(query_type: str, query_used: str, input_title: str, input_artist: str) -> str:
    query_norm = normalize_title(query_used)
    title_norm = normalize_title(input_title)
    artist_parts = _split_artist_parts(input_artist)
    title_present = bool(title_norm and title_norm in query_norm)
    artist_present = bool(
        input_artist
        and any(normalize_title(part) and normalize_title(part) in query_norm for part in artist_parts)
    )
    if title_present and artist_present:
        return "high" if query_type == "primary" else "medium"
    return "low"


def _input_candidate_token_overlap(input_title: str, input_artist: str, candidate_title: str, candidate_artists: List[str]) -> float:
    return _token_overlap_ratio(
        f"{input_artist} {input_title}",
        f"{' '.join(candidate_artists)} {candidate_title}",
    )


def _looks_like_uppercase_english(value: str) -> bool:
    letters = re.findall(r"[A-Za-z]", value or "")
    return bool(letters) and len(letters) >= 3 and "".join(letters).upper() == "".join(letters)


def _looks_like_english_title(value: str) -> bool:
    normalized = normalize_title(value)
    tokens = [token for token in normalized.split() if token]
    if not tokens or _has_korean(value):
        return False
    return bool(_has_english(value) and 1 <= len(tokens) <= 6)


def _candidate_has_blocking_version(candidate_title: str, candidate_artists: List[str], detail: Dict[str, Any]) -> bool:
    haystack = _candidate_text(candidate_title, candidate_artists)
    return (
        "non_original_audio_pattern" in set(detail.get("pattern_tags", []))
        or _contains_keyword(haystack, NON_ORIGINAL_KEYWORDS)
        or any(keyword in haystack for keyword in {"remix", "prod by", "produced by", "instrumental", "cover", "tribute"})
    )


def _candidate_evidence(
    *,
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    detail: Dict[str, Any],
) -> Tuple[List[str], List[str], Dict[str, float]]:
    title_score = float(detail.get("title_variant_score", detail.get("title_score", 0.0)))
    artist_score = float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)))
    token_score = _input_candidate_token_overlap(input_title, input_artist, candidate_title, candidate_artists)
    matched: List[str] = []
    missing: List[str] = []

    checks = {
        "artist_alias_match": bool(detail.get("artist_alias_matched")),
        "artist_romanization_match": (
            bool(input_artist)
            and _has_korean(input_artist)
            and any(_has_english(artist) for artist in candidate_artists)
            and (
                artist_score >= 0.72
                or bool(detail.get("romanization_matched"))
                or normalize_artist(resolve_artist_alias(input_artist)) in {
                    normalize_artist(artist) for artist in candidate_artists
                }
            )
        ),
        "title_direct_match": title_score >= 0.55,
        "token_overlap": token_score > 0,
    }

    for key, value in checks.items():
        (matched if value else missing).append(key)

    return matched, missing, {
        "title_score": title_score,
        "artist_score": artist_score,
        "token_score": token_score,
    }


def _mark_invalid_candidate(
    *,
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    detail: Dict[str, Any],
    source: Dict[str, str],
    api_rank: int,
) -> Dict[str, Any]:
    matched_evidence, missing_evidence, scores = _candidate_evidence(
        input_title=input_title,
        input_artist=input_artist,
        candidate_title=candidate_title,
        candidate_artists=candidate_artists,
        detail=detail,
    )
    invalid = {
        **detail,
        "pattern": "invalid_candidate",
        "pattern_tags": ["invalid_candidate"],
        "match_status": "invalid_candidate",
        "matched_evidence": matched_evidence,
        "missing_evidence": missing_evidence,
        "blocked_reason": f"artist_score={scores['artist_score']:.4f} and title_score={scores['title_score']:.4f}; no evidence",
        "candidate_decision": "rejected",
        "api_rank": api_rank + 1,
        "query_type": source.get("query_type", "primary" if api_rank == 0 else "fallback"),
        "query_used": source.get("query_used", ""),
        "query_reliability": _query_reliability(
            source.get("query_type", "primary" if api_rank == 0 else "fallback"),
            source.get("query_used", ""),
            input_title,
            input_artist,
        ),
        "search_engine_signal": False,
        "search_engine_signal_score": 0.0,
        "search_engine_signal_reason": "",
        "search_engine_signal_blocked_reason": "invalid_candidate",
        "rank_bonus_applied": False,
        "notation_difference_detected": False,
        "notation_difference_reason": "",
        "score_before_search_engine_signal": scores["title_score"],
        "query_contains_title_and_artist": False,
        "input_candidate_token_overlap": scores["token_score"],
        "title_variant_score": scores["title_score"],
        "artist_variant_score": scores["artist_score"],
        "final_score": 0.0,
        "bonuses": {},
        "penalties": {},
        "score_caps": {},
    }
    return invalid


def _evidence_score_detail(candidate: Dict[str, Any]) -> Dict[str, Any]:
    detail = candidate.get("score_detail", {}) or {}
    pattern_tags = set(detail.get("pattern_tags", []))
    title_score = float(detail.get("title_variant_score", detail.get("title_score", 0.0)) or 0.0)
    artist_score = float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)) or 0.0)
    token_score = float(detail.get("input_candidate_token_overlap", detail.get("token_score", 0.0)) or 0.0)
    api_rank = int(detail.get("api_rank", 999) or 999)
    query_reliability = str(detail.get("query_reliability") or "low")
    title_alias = bool(detail.get("title_alias_matched"))
    artist_alias = bool(detail.get("artist_alias_matched"))
    romanization = bool(detail.get("romanization_matched")) or "artist_romanization_match" in detail.get("matched_evidence", [])
    official_metadata = bool(detail.get("official_metadata_candidate"))

    if detail.get("pattern") == "invalid_candidate":
        return {
            "title_evidence": {
                "type": "mismatch",
                "score": 0.0,
                "reason": "제목 유사도 또는 별칭 근거가 없습니다.",
            },
            "artist_evidence": {
                "type": "mismatch",
                "score": 0.0,
                "reason": "가수 별칭/로마자 근거가 없습니다.",
            },
            "query_evidence": {
                "type": "none",
                "score": 0.0,
                "reason": "기본 근거가 없어 검색 순위 근거를 적용하지 않았습니다.",
                "applied": False,
            },
            "metadata_evidence": {
                "album_image": bool(candidate.get("album_image")),
                "duration_close": None,
                "score": 0.0,
            },
            "risk_penalty": {
                "score": 0.0,
                "reasons": [],
            },
            "pattern": "invalid_candidate",
            "score_cap": 0.0,
            "final_score": 0.0,
            "decision": "rejected",
        }

    if title_alias:
        title_evidence = {"type": "alias", "score": 0.45, "reason": "곡명이 title alias로 일치합니다."}
    elif official_metadata:
        title_evidence = {
            "type": "translation_alias",
            "score": 0.25,
            "reason": "Spotify API에서 영어/로마자 공식 제목으로 반환된 후보입니다.",
        }
    elif title_score >= 0.95:
        title_evidence = {"type": "exact", "score": 0.45, "reason": "곡명이 정확히 일치합니다."}
    elif title_score >= 0.55:
        title_evidence = {
            "type": "partial",
            "score": round(min(0.32, title_score * 0.32), 4),
            "reason": "곡명 일부가 유사합니다.",
        }
    else:
        title_evidence = {"type": "mismatch", "score": 0.0, "reason": "곡명 유사도가 낮습니다."}

    if artist_alias:
        artist_evidence = {"type": "alias", "score": 0.35, "reason": "가수명이 artist alias로 일치합니다."}
    elif romanization:
        artist_evidence = {"type": "romanization", "score": 0.33, "reason": "가수명이 로마자 표기상 일치합니다."}
    elif artist_score >= 0.95:
        artist_evidence = {"type": "exact", "score": 0.35, "reason": "가수명이 정확히 일치합니다."}
    elif artist_score >= 0.55:
        artist_evidence = {
            "type": "partial",
            "score": round(min(0.25, artist_score * 0.25), 4),
            "reason": "가수명 일부가 유사합니다.",
        }
    else:
        artist_evidence = {"type": "mismatch", "score": 0.0, "reason": "가수명 유사도가 낮습니다."}

    base_evidence_exists = not (
        title_evidence["type"] == "mismatch"
        and artist_evidence["type"] == "mismatch"
    )
    query_applied = (
        base_evidence_exists
        and api_rank == 1
        and query_reliability in {"high", "medium"}
    )
    if query_applied:
        query_type = "rank1_alias_query" if (title_alias or artist_alias or romanization) else "rank1_original_query"
        query_evidence = {
            "type": query_type,
            "score": 0.15 if query_reliability == "high" else 0.10,
            "reason": "검색 1위 후보이며 기본 매칭 근거가 있어 보조 근거로 반영했습니다.",
            "applied": True,
        }
    else:
        query_evidence = {
            "type": "none",
            "score": 0.0,
            "reason": "검색 순위는 단독 근거로 사용하지 않습니다.",
            "applied": False,
        }

    metadata_score = 0.03 if candidate.get("album_image") else 0.0
    metadata_evidence = {
        "album_image": bool(candidate.get("album_image")),
        "duration_close": None,
        "score": metadata_score,
    }

    penalty_reasons: List[str] = []
    penalty_score = 0.0
    if "non_original_audio_pattern" in pattern_tags:
        penalty_score += 0.35
        penalty_reasons.append("원곡이 아닌 버전일 가능성이 있습니다.")
    if "short_title_false_positive_pattern" in pattern_tags:
        penalty_score += 0.20
        penalty_reasons.append("짧은 제목으로 인한 오탐 가능성이 있습니다.")
    if "title_only_overconfidence_pattern" in pattern_tags:
        penalty_score += 0.12
        penalty_reasons.append("제목만 유사하고 가수 근거가 약합니다.")
    if "artist_only_overconfidence_pattern" in pattern_tags:
        penalty_score += 0.12
        penalty_reasons.append("가수만 유사하고 제목 근거가 약합니다.")

    raw_score = (
        float(title_evidence["score"])
        + float(artist_evidence["score"])
        + float(query_evidence["score"])
        + metadata_score
        - penalty_score
    )

    if title_evidence["type"] in {"exact", "alias"} and artist_evidence["type"] in {"exact", "alias", "romanization"}:
        pattern = "strong_match"
        score_cap = 1.0
    elif official_metadata and artist_evidence["type"] in {"alias", "romanization", "exact"}:
        pattern = "official_metadata_candidate"
        score_cap = 0.79
    elif title_evidence["type"] != "mismatch" and artist_evidence["type"] != "mismatch":
        pattern = "probable_match"
        score_cap = 0.86
    elif title_evidence["type"] != "mismatch" or artist_evidence["type"] != "mismatch":
        pattern = "weak_evidence"
        score_cap = 0.74 if query_applied else 0.60
    else:
        pattern = "invalid_candidate"
        score_cap = 0.0

    final_score = max(0.0, min(round(raw_score, 4), score_cap))
    if pattern == "strong_match" and final_score >= 0.78:
        decision = "auto_select_recommended"
    elif pattern in {"probable_match", "official_metadata_candidate"} and final_score >= 0.55:
        decision = "confirm_before_select"
    elif pattern == "weak_evidence" and final_score > 0:
        decision = "warning"
    else:
        decision = "rejected"

    return {
        "title_evidence": title_evidence,
        "artist_evidence": artist_evidence,
        "query_evidence": query_evidence,
        "metadata_evidence": metadata_evidence,
        "risk_penalty": {
            "score": round(penalty_score, 4),
            "reasons": penalty_reasons,
        },
        "pattern": pattern,
        "score_cap": score_cap,
        "final_score": final_score,
        "decision": decision,
    }


def _apply_evidence_score(candidate: Dict[str, Any]) -> Dict[str, Any]:
    evidence_detail = _evidence_score_detail(candidate)
    enriched = dict(candidate)
    score_detail = dict(enriched.get("score_detail", {}))
    score_detail["evidence_confidence"] = evidence_detail
    score_detail["pattern"] = evidence_detail["pattern"]
    score_detail["score_cap"] = evidence_detail["score_cap"]
    score_detail["final_score"] = evidence_detail["final_score"]
    score_detail["candidate_decision"] = evidence_detail["decision"]
    score_detail["rank_bonus_applied"] = bool(evidence_detail["query_evidence"]["applied"])
    enriched["score_detail"] = score_detail
    enriched["score"] = evidence_detail["final_score"]
    return enriched


def _official_metadata_signal(
    *,
    input_title: str,
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    detail = candidate.get("score_detail", {})
    candidate_title = candidate.get("name", "")
    candidate_artists = candidate.get("artists", [])
    title_variant_score = float(detail.get("title_variant_score", detail.get("title_score", 0.0)))
    artist_variant_score = float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)))
    api_rank = int(detail.get("api_rank", 999))
    reliability = str(detail.get("query_reliability", "low"))
    has_album_image = bool(candidate.get("album_image"))
    popularity = int(candidate.get("popularity") or 0)
    duration_ms = candidate.get("duration_ms")
    title_alias = bool(detail.get("title_alias_matched"))
    artist_support = (
        artist_variant_score >= 0.72
        or bool(detail.get("artist_alias_matched"))
        or bool(detail.get("romanization_matched"))
    )
    metadata_display_gap = (
        bool(input_title)
        and _has_korean(input_title)
        and _has_english(candidate_title)
        and not _has_korean(candidate_title)
        and title_variant_score < 0.65
        and not title_alias
    )
    evidence_count = sum(
        [
            api_rank == 1,
            reliability in {"high", "medium"},
            artist_support,
            has_album_image,
            popularity >= 20,
            bool(detail.get("query_contains_title_and_artist")),
            bool(detail.get("search_engine_signal")),
            duration_ms is not None,
        ]
    )
    detected = (
        metadata_display_gap
        and api_rank == 1
        and reliability in {"high", "medium"}
        and artist_support
        and evidence_count >= 4
        and not _candidate_has_blocking_version(candidate_title, candidate_artists, detail)
    )

    return {
        "official_metadata_candidate": detected,
        "official_metadata_reason": "official_spotify_metadata_candidate" if detected else "",
        "official_metadata_evidence": {
            "api_rank": api_rank,
            "query_reliability": reliability,
            "artist_variant_score": round(artist_variant_score, 4),
            "title_variant_score": round(title_variant_score, 4),
            "album_image_exists": has_album_image,
            "duration_ms": duration_ms,
            "duration_delta_ms": None,
            "popularity": popularity,
            "query_contains_title_and_artist": bool(detail.get("query_contains_title_and_artist")),
            "search_engine_signal": bool(detail.get("search_engine_signal")),
        },
    }


def detect_notation_difference(
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    api_rank: int,
    query_reliability: str,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    title_score = float(detail.get("title_variant_score", detail.get("title_score", 0.0)))
    artist_score = float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)))
    candidate_artist_text = " ".join(candidate_artists)
    reasons: List[str] = []

    if _has_korean(input_title) and _has_english(candidate_title) and not _has_korean(candidate_title):
        reasons.append("korean_title_english_candidate")
    if _has_korean(input_artist) and _has_english(candidate_artist_text) and not _has_korean(candidate_artist_text):
        reasons.append("korean_artist_romanized_candidate")
    if (_has_korean(input_title) or _has_korean(input_artist)) and (
        _looks_like_uppercase_english(candidate_title) or any(_looks_like_uppercase_english(artist) for artist in candidate_artists)
    ):
        reasons.append("korean_input_uppercase_english_candidate")
    if _has_korean(input_title) and _looks_like_english_title(candidate_title):
        reasons.append("official_english_title_shape")
    if _has_korean(input_artist) and any(_looks_like_english_title(artist) for artist in candidate_artists):
        reasons.append("romanized_artist_shape")
    if api_rank == 1 and query_reliability in {"high", "medium"} and title_score < 0.45 and artist_score < 0.45 and reasons:
        reasons.append("low_string_score_rank1_reliable_query")

    has_explicit_evidence = (
        bool(detail.get("artist_alias_matched"))
        or bool(detail.get("title_alias_matched"))
        or title_score >= 0.55
        or (
            _has_korean(input_artist)
            and _has_english(candidate_artist_text)
            and artist_score >= 0.55
        )
    )
    detected = bool(reasons) and has_explicit_evidence
    return {
        "notation_difference_detected": detected,
        "notation_difference_reason": ",".join(reasons) if reasons else "",
    }


def _has_strong_evidence(detail: Dict[str, Any]) -> bool:
    return (
        float(detail.get("artist_variant_score", detail.get("artist_score", 0.0))) >= 0.80
        or float(detail.get("title_variant_score", detail.get("title_score", 0.0))) >= 0.80
        or bool(detail.get("artist_alias_matched"))
        or bool(detail.get("title_alias_matched"))
        or bool(detail.get("romanization_matched"))
        or float(detail.get("input_candidate_token_overlap", 0.0)) > 0
        or (
            detail.get("query_reliability") == "high"
            and bool(detail.get("notation_difference_detected"))
        )
    )


def apply_search_engine_signal(
    score: float,
    detail: Dict[str, Any],
    *,
    input_title: str,
    input_artist: str,
    candidate_title: str,
    candidate_artists: List[str],
    api_rank: int,
    query_type: str,
    query_used: str,
) -> Tuple[float, Dict[str, Any]]:
    enriched = dict(detail)
    title_variant_score = float(enriched.get("title_variant_score", enriched.get("title_score", 0.0)))
    artist_variant_score = float(enriched.get("artist_variant_score", enriched.get("artist_score", 0.0)))
    query_has_title_artist = _query_contains_title_and_artist(query_used, input_title, input_artist)
    reliability = _query_reliability(query_type, query_used, input_title, input_artist)
    notation = detect_notation_difference(
        input_title,
        input_artist,
        candidate_title,
        candidate_artists,
        api_rank,
        reliability,
        enriched,
    )
    enriched.update(notation)
    title_support = (
        title_variant_score >= 0.72
        or bool(enriched.get("title_alias_matched"))
        or bool(enriched.get("title_exact_match"))
    )
    artist_support = (
        not input_artist
        or artist_variant_score >= 0.60
        or bool(enriched.get("artist_alias_matched"))
        or bool(enriched.get("artist_exact_match"))
    )
    token_overlap = _input_candidate_token_overlap(input_title, input_artist, candidate_title, candidate_artists)
    notation_possible = bool(enriched.get("notation_difference_detected")) or bool(enriched.get("romanization_matched"))
    signal_score = 0.0
    reason = ""
    blocked_reason = ""

    if api_rank != 1:
        blocked_reason = "not_rank1"
    elif reliability == "low":
        blocked_reason = "low_query_reliability"
    elif _candidate_has_blocking_version(candidate_title, candidate_artists, enriched):
        blocked_reason = "non_original_or_version_candidate"
    elif title_variant_score >= 0.95 and input_artist and artist_variant_score < MIN_ARTIST_SCORE and not bool(enriched.get("artist_alias_matched")):
        blocked_reason = "title_exact_artist_mismatch"
    elif artist_variant_score >= 0.95 and title_variant_score < 0.35 and not (bool(enriched.get("title_alias_matched")) or notation_possible):
        blocked_reason = "artist_exact_title_mismatch"
    elif title_variant_score >= 0.95 and input_artist and not artist_support:
        blocked_reason = "possible_same_title_different_artist"
    elif not (title_support or artist_support or token_overlap > 0 or notation_possible):
        blocked_reason = "no_explainable_title_or_artist_evidence"
    else:
        if reliability == "high" and query_has_title_artist and artist_support:
            signal_score = 0.22
            reason = "high_query_rank1_artist_variant_alias_or_romanization"
        elif reliability == "high" and query_has_title_artist and title_support:
            signal_score = 0.22
            reason = "high_query_rank1_title_variant_alias_or_romanization"
        elif reliability == "high" and query_has_title_artist and notation_possible:
            signal_score = 0.18
            reason = "high_query_rank1_notation_difference"
        elif reliability == "medium" and notation_possible:
            signal_score = 0.14
            reason = "medium_query_rank1_notation_difference"

    score_before_signal = round(score, 4)
    final_score = score
    if signal_score > 0:
        final_score = min(1.0, score + signal_score)
        if score < REVIEW_NEEDED_SCORE and reliability == "high" and notation_possible and query_has_title_artist:
            final_score = max(final_score, REVIEW_NEEDED_SCORE)
        if reliability == "high" and (title_support or artist_support) and notation_possible:
            final_score = max(final_score, 0.75)
        if title_variant_score >= 0.95 and artist_variant_score >= 0.70 and _has_strong_evidence({**enriched, "input_candidate_token_overlap": token_overlap}):
            final_score = max(final_score, 0.82)
        if reason and "search_engine_signal_pattern" not in enriched.get("pattern_tags", []):
            enriched["pattern_tags"] = list(enriched.get("pattern_tags", [])) + ["search_engine_signal_pattern"]

    final_score = max(0.0, min(round(final_score, 4), 1.0))
    enriched.update({
        "api_rank": api_rank,
        "query_type": query_type,
        "query_used": query_used,
        "query_reliability": reliability,
        "search_engine_signal": signal_score > 0,
        "search_engine_signal_score": round(signal_score, 4),
        "search_engine_signal_reason": reason,
        "search_engine_signal_blocked_reason": blocked_reason,
        "score_before_search_engine_signal": score_before_signal,
        "query_contains_title_and_artist": query_has_title_artist,
        "input_candidate_token_overlap": token_overlap,
        "final_score": final_score,
    })
    return final_score, enriched


def decide_match_status(score: float) -> str:
    return _status_from_score(score)


def rank_candidates(scored_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        scored_candidates,
        key=lambda item: (
            item["score"],
            item["score_detail"].get("search_engine_signal_score", 0.0),
            QUERY_RELIABILITY_WEIGHT.get(str(item["score_detail"].get("query_reliability", "low")), 1),
            item["score_detail"].get("artist_variant_score", item["score_detail"].get("artist_score", 0.0)),
            item["score_detail"].get("title_variant_score", item["score_detail"].get("title_score", 0.0)),
            -int(item["score_detail"].get("api_rank", 999)),
            item.get("popularity", 0),
        ),
        reverse=True,
    )


def _candidate_reason(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> str:
    detail = candidate.get("score_detail", {})
    pattern_tags = set(detail.get("pattern_tags", []))
    title_score = float(detail.get("title_variant_score", detail.get("title_score", 0.0)))
    artist_score = float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)))
    version_penalty = float(detail.get("version_penalty", 0.0))
    score = float(candidate.get("score", 0.0))
    artist_alias_matched = bool(detail.get("artist_alias_matched", False))

    if detail.get("pattern") == "invalid_candidate" or "invalid_candidate" in pattern_tags:
        return "invalid_candidate"
    if bool(detail.get("official_metadata_candidate")):
        return "official_spotify_metadata_candidate"
    if "non_original_audio_pattern" in pattern_tags:
        return "non_original_audio"
    if "artist_only_overconfidence_pattern" in pattern_tags:
        return "artist_only_overconfidence"
    if "title_only_overconfidence_pattern" in pattern_tags:
        return "title_only_overconfidence"
    if "short_title_false_positive_pattern" in pattern_tags:
        return "short_title_false_positive"
    if version_penalty >= 0.08 or "acceptable_version_pattern" in pattern_tags:
        return "version_candidate"
    if score >= DIRECT_ACCEPT_SCORE:
        return "matched"
    if has_artist and title_score >= 0.95 and artist_score < MIN_ARTIST_SCORE:
        return "title_matched_artist_alias_candidate"
    if has_artist and artist_score >= 0.95 and title_score < MIN_TITLE_SCORE:
        return "artist_matched_title_mismatch"
    if (
        has_artist
        and int(candidate.get("candidate_rank", 999)) == 0
        and title_score < TITLE_MISMATCH_MAX_TITLE_SCORE
        and _possible_artist_romanization_match(input_artist, candidate.get("artists", []))
        and not (artist_score >= TITLE_MISMATCH_ARTIST_SCORE or artist_alias_matched)
    ):
        return "top_candidate_artist_romanization_title_mismatch"
    if title_score < 0.40 and (not has_artist or artist_score < 0.40):
        return "weak_title_and_artist"
    if title_score < MIN_TITLE_SCORE:
        return "title_mismatch"
    if has_artist and artist_score < MIN_ARTIST_SCORE:
        return "artist_mismatch"
    if score >= REVIEW_NEEDED_SCORE:
        return "partial_match_needs_review"
    return "low_score"

def _log_match(
    *,
    input_title: str,
    input_artist: str,
    cache_status: str,
    chosen_case: str,
    queries: List[str],
    fallback_used: bool,
    candidate_count: int,
    selected: str,
    selected_score: float,
    reason: str,
    unmatched_reason: str,
    early_return: bool,
) -> None:
    extra = f" unmatched_reason='{unmatched_reason}'" if unmatched_reason else ""
    print(
        f"[spotify-match] input='{input_artist} - {input_title}' "
        f"chosen_case={chosen_case} queries={queries} fallback_used={str(fallback_used).lower()} "
        f"cache={cache_status} candidates={candidate_count} selected='{selected}' "
        f"score={selected_score:.4f} reason='{reason}'{extra} "
        f"early_return={str(early_return).lower()}"
    )


def _track_dedupe_key(track: Dict[str, Any]) -> Tuple[Any, ...]:
    artists = tuple((artist or {}).get("name", "") for artist in track.get("artists", []))
    return (
        track.get("id") or "",
        track.get("uri") or "",
        track.get("name", ""),
        artists,
    )


def _build_case_queries(title: str, artist: str) -> List[Dict[str, str]]:
    primary_title = ""
    title_variants = build_title_search_variants(title)
    for variant in title_variants:
        variant = (variant or "").strip()
        if variant:
            primary_title = variant
            break
    if not primary_title:
        primary_title = (title or "").strip()

    primary_artist = ""
    artist_variants = build_artist_search_variants(artist)
    if artist_variants:
        primary_artist = artist_variants[0]
    elif artist:
        primary_artist = resolve_artist_alias(artist)

    queries: List[Dict[str, str]] = []

    if primary_title and primary_artist:
        queries.append(
            {
                "mode": "track_artist",
                "title": primary_title,
                "artist": primary_artist,
                "query": f'track:"{primary_title}" artist:"{primary_artist}"',
            }
        )
    elif primary_title:
        queries.append(
            {
                "mode": "track_only",
                "title": primary_title,
                "artist": "",
                "query": f'track:"{primary_title}"',
            }
        )

    fallback_query = " ".join(part for part in [primary_title, primary_artist] if part).strip()
    if fallback_query and len(queries) < MAX_QUERY_COUNT:
        if not queries or fallback_query != queries[0]["query"]:
            queries.append(
                {
                    "mode": "query",
                    "title": primary_title,
                    "artist": primary_artist,
                    "query": fallback_query,
                }
            )

    return queries[:MAX_QUERY_COUNT]


def _score_tracks(
    raw_tracks: List[Dict[str, Any]],
    track_sources: Dict[Tuple[Any, ...], Dict[str, str]],
    *,
    input_title: str,
    input_artist: str,
    chosen_case: str,
) -> List[Dict[str, Any]]:
    unique_tracks: List[Dict[str, Any]] = []
    seen_keys = set()
    for track in raw_tracks:
        key = _track_dedupe_key(track)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_tracks.append(track)

    scored_candidates: List[Dict[str, Any]] = []
    for api_rank, track in enumerate(unique_tracks):
        base_score, detail = calculate_base_score(input_title, input_artist, track)
        track_name = track.get("name", "")
        track_artists = [artist.get("name", "") for artist in track.get("artists", [])]
        source = track_sources.get(_track_dedupe_key(track), {})
        detail = _enrich_variant_detail(
            input_title=input_title,
            input_artist=input_artist,
            candidate_title=track_name,
            candidate_artists=track_artists,
            detail=detail,
        )
        matched_evidence, missing_evidence, _evidence_scores = _candidate_evidence(
            input_title=input_title,
            input_artist=input_artist,
            candidate_title=track_name,
            candidate_artists=track_artists,
            detail=detail,
        )
        if not matched_evidence:
            invalid_detail = _mark_invalid_candidate(
                input_title=input_title,
                input_artist=input_artist,
                candidate_title=track_name,
                candidate_artists=track_artists,
                detail=detail,
                source=source,
                api_rank=api_rank,
            )
            candidate = _candidate_to_result(
                track,
                0.0,
                invalid_detail,
                search_title=source.get("search_title", input_title),
                search_artist=source.get("search_artist", input_artist),
                chosen_case=chosen_case,
            )
            candidate["match_status"] = "invalid_candidate"
            candidate["unmatched_reason"] = "invalid_candidate"
            candidate["user_message"] = _reason_message("invalid_candidate")
            candidate = _apply_evidence_score(candidate)
            candidate["candidate_rank"] = len(scored_candidates)
            scored_candidates.append(candidate)
            continue

        pattern_tags = classify_candidate_patterns(
            input_title=input_title,
            input_artist=input_artist,
            candidate_title=track_name,
            candidate_artists=track_artists,
            detail=detail,
            base_score=base_score,
            api_rank=api_rank,
        )

        score, detail = apply_pattern_adjustments(
            base_score,
            detail,
            pattern_tags,
        )
        score, detail = apply_search_engine_signal(
            score,
            detail,
            input_title=input_title,
            input_artist=input_artist,
            candidate_title=track_name,
            candidate_artists=track_artists,
            api_rank=api_rank + 1,
            query_type=source.get("query_type", "primary" if api_rank == 0 else "fallback"),
            query_used=source.get("query_used", ""),
        )
        detail["score_before_context"] = round(base_score, 4)
        detail["matched_evidence"] = matched_evidence
        detail["missing_evidence"] = missing_evidence
        detail["blocked_reason"] = detail.get("search_engine_signal_blocked_reason", "")
        detail["rank_bonus_applied"] = bool(detail.get("search_engine_signal"))
        detail["candidate_decision"] = "selectable"
        candidate = _candidate_to_result(
                track,
                score,
                detail,
                search_title=source.get("search_title", input_title),
                search_artist=source.get("search_artist", input_artist),
                chosen_case=chosen_case,
            )
        metadata_signal = _official_metadata_signal(
            input_title=input_title,
            candidate=candidate,
        )
        candidate["score_detail"] = {
            **candidate["score_detail"],
            **metadata_signal,
        }
        if metadata_signal["official_metadata_candidate"]:
            candidate["score"] = max(float(candidate.get("score", 0.0)), PROBABLE_MATCH_SCORE)
            candidate["score_detail"]["final_score"] = candidate["score"]
        candidate = _apply_evidence_score(candidate)
        candidate["candidate_rank"] = len(scored_candidates)
        scored_candidates.append(candidate)

    return rank_candidates(scored_candidates)


def _classify_candidate(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> str:
    """Classify a Spotify candidate without making extra searches."""
    score = float(candidate.get("score", 0.0))
    detail = candidate.get("score_detail", {})
    pattern_tags = set(detail.get("pattern_tags", []))
    if detail.get("pattern") == "invalid_candidate" or "invalid_candidate" in pattern_tags:
        return "invalid_candidate"
    evidence = detail.get("evidence_confidence") or {}
    decision = evidence.get("decision") or detail.get("candidate_decision")
    pattern = evidence.get("pattern") or detail.get("pattern")
    if decision == "auto_select_recommended":
        return "matched"
    if decision == "confirm_before_select":
        return "probable_match"
    if decision == "warning" or pattern == "weak_evidence":
        return "review_needed"
    if decision == "rejected":
        return "unmatched"
    api_rank = int(detail.get("api_rank", 999))
    low_confidence_search_candidate = (
        api_rank == 1
        and score >= 0.15
        and "non_original_audio_pattern" not in pattern_tags
        and "short_title_false_positive_pattern" not in pattern_tags
    )
    notation_or_romanization_candidate = (
        score >= 0.15
        and (
            bool(detail.get("romanization_matched"))
            or bool(detail.get("notation_difference_detected"))
            or "notation_difference_pattern" in pattern_tags
        )
        and "non_original_audio_pattern" not in pattern_tags
    )
    if (
        "title_only_overconfidence_pattern" in pattern_tags
        and float(detail.get("artist_variant_score", detail.get("artist_score", 0.0))) < MIN_ARTIST_SCORE
        and not bool(detail.get("artist_alias_matched"))
        and not bool(detail.get("romanization_matched"))
    ):
        return "review_needed" if score >= REVIEW_NEEDED_SCORE else "unmatched"
    if (
        "artist_only_overconfidence_pattern" in pattern_tags
        and float(detail.get("title_variant_score", detail.get("title_score", 0.0))) < MIN_TITLE_SCORE
        and not bool(detail.get("title_alias_matched"))
        and not bool(detail.get("notation_difference_detected"))
    ):
        return "review_needed" if score >= REVIEW_NEEDED_SCORE else "unmatched"
    if score >= 0.82 and _has_strong_evidence(detail):
        if bool(detail.get("official_metadata_candidate")) and not bool(detail.get("title_alias_matched")):
            return "probable_match"
        return "matched"
    if (
        score >= 0.75
        and bool(detail.get("search_engine_signal"))
        and detail.get("query_reliability") == "high"
        and _has_strong_evidence(detail)
    ):
        return "probable_match"
    if score >= REVIEW_NEEDED_SCORE and bool(detail.get("search_engine_signal")):
        return "review_needed"
    if score >= PROBABLE_MATCH_SCORE and _has_strong_evidence(detail):
        return "probable_match"
    if low_confidence_search_candidate or notation_or_romanization_candidate:
        return "review_needed"
    if score >= REVIEW_NEEDED_SCORE and "weak_both_pattern" not in set(detail.get("pattern_tags", [])):
        return "review_needed"
    return "unmatched"


def _candidate_is_acceptable(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> bool:
    return _classify_candidate(candidate, has_artist=has_artist, input_artist=input_artist) in {
        "matched",
        "probable_match",
    }


def _candidate_is_recoverable(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> bool:
    return _classify_candidate(candidate, has_artist=has_artist, input_artist=input_artist) in {
        "review_needed",
    }


def _low_confidence_reason_for_status(candidate: Dict[str, Any], status: str, *, has_artist: bool, input_artist: str = "") -> str:
    if bool(candidate.get("score_detail", {}).get("official_metadata_candidate")):
        return "official_spotify_metadata_candidate"
    if status in {"matched", "probable_match"}:
        return ""
    return _candidate_reason(candidate, has_artist=has_artist, input_artist=input_artist)


def _attach_candidate_status(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> Dict[str, Any]:
    enriched = dict(candidate)
    status = _classify_candidate(candidate, has_artist=has_artist, input_artist=input_artist)
    reason = _candidate_reason(candidate, has_artist=has_artist, input_artist=input_artist)
    enriched["match_status"] = status
    enriched["user_message"] = _reason_message(reason if status == "unmatched" else status)
    enriched["unmatched_reason"] = reason if status == "unmatched" else ""
    score_detail = dict(enriched.get("score_detail", {}))
    if status == "invalid_candidate":
        score_detail["candidate_decision"] = "rejected"
    elif status == "review_needed":
        score_detail["candidate_decision"] = "warning"
    else:
        score_detail["candidate_decision"] = "selectable"
    enriched["score_detail"] = score_detail
    if status != "matched":
        enriched["low_confidence"] = status in {"probable_match", "review_needed"}
        enriched["low_confidence_reason"] = _low_confidence_reason_for_status(
            candidate,
            status,
            has_artist=has_artist,
            input_artist=input_artist,
        )
        if enriched["low_confidence_reason"]:
            enriched["user_message"] = _reason_message(enriched["low_confidence_reason"])
    return enriched


def _pick_best_acceptable_candidate(
    scored_candidates: List[Dict[str, Any]],
    *,
    has_artist: bool,
    input_artist: str = "",
) -> Optional[Dict[str, Any]]:
    matched = [
        _attach_candidate_status(candidate, has_artist=has_artist, input_artist=input_artist)
        for candidate in scored_candidates
        if _candidate_is_acceptable(candidate, has_artist=has_artist, input_artist=input_artist)
    ]
    if matched:
        return max(
            matched,
            key=lambda item: (
                item["score"],
                item.get("popularity", 0),
                item["score_detail"].get("title_score", 0.0),
                item["score_detail"].get("artist_score", 0.0),
            ),
        )

    recoverable = [
        _attach_candidate_status(candidate, has_artist=has_artist, input_artist=input_artist)
        for candidate in scored_candidates
        if _candidate_is_recoverable(candidate, has_artist=has_artist, input_artist=input_artist)
    ]
    if not recoverable:
        invalid = [
            _attach_candidate_status(candidate, has_artist=has_artist, input_artist=input_artist)
            for candidate in scored_candidates
            if _classify_candidate(candidate, has_artist=has_artist, input_artist=input_artist) == "invalid_candidate"
        ]
        if invalid:
            return invalid[0]
        return None

    status_priority = {
        "review_needed": 2,
        "unmatched": 0,
    }
    return max(
        recoverable,
        key=lambda item: (
            status_priority.get(item.get("match_status", "unmatched"), 0),
            item["score"],
            item["score_detail"].get("title_score", 0.0),
            item["score_detail"].get("artist_score", 0.0),
            item.get("popularity", 0),
        ),
    )

def _build_unmatched_reason(
    scored_candidates: List[Dict[str, Any]],
    *,
    has_artist: bool,
    input_artist: str = "",
) -> str:
    if not scored_candidates:
        return "no_search_result"

    best = scored_candidates[0]
    status = _classify_candidate(best, has_artist=has_artist, input_artist=input_artist)
    detail = best.get("score_detail", {})
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    score = float(best.get("score", 0.0))

    if status in {"matched", "probable_match"}:
        return ""
    reason = _candidate_reason(best, has_artist=has_artist, input_artist=input_artist)
    return f"{reason}(score={score:.2f},title={title_score:.2f},artist={artist_score:.2f})"

def _summarize_case_result(case_result: Dict[str, Any]) -> Dict[str, Any]:
    best = case_result.get("best_candidate") or {}
    return {
        "case_name": case_result.get("case_name", "original"),
        "input_title": case_result.get("input_title", ""),
        "input_artist": case_result.get("input_artist", ""),
        "queries": case_result.get("queries", []),
        "fallback_used": case_result.get("fallback_used", False),
        "best_score": best.get("score", 0.0),
        "matched_name": best.get("name", ""),
        "matched_artists": best.get("artists", []),
        "unmatched_reason": case_result.get("unmatched_reason", ""),
    }


def _store_match_debug(
    cache_key: Tuple[str, str],
    *,
    selected_case: str,
    search_title: str,
    search_artist: str,
    unmatched_reason: str,
    top_candidates: List[Dict[str, Any]],
    case_results: List[Dict[str, Any]],
) -> None:
    _MATCH_DEBUG[cache_key] = {
        "selected_case": selected_case,
        "search_title": search_title,
        "search_artist": search_artist,
        "unmatched_reason": unmatched_reason,
        "case_results": [_summarize_case_result(case_result) for case_result in case_results],
        "top_candidates": [
            {
                "name": candidate.get("name", ""),
                "artists": candidate.get("artists", []),
                "score": candidate.get("score", 0.0),
                "popularity": candidate.get("popularity", 0),
                "score_detail": candidate.get("score_detail", {}),
                "chosen_case": candidate.get("chosen_case", selected_case),
                "match_status": candidate.get("match_status", ""),
                "low_confidence_reason": candidate.get("low_confidence_reason", ""),
                "unmatched_reason": candidate.get("unmatched_reason", ""),
                "user_message": candidate.get("user_message", ""),
            }
            for candidate in top_candidates[:3]
        ],
    }


def get_match_debug(title: str, artist: str) -> Dict[str, Any]:
    cache_key = build_match_cache_key(title, artist)
    return dict(_MATCH_DEBUG.get(cache_key, {}))


def _evaluate_case(
    access_token: str,
    *,
    case_name: str,
    title: str,
    artist: str,
    market: Optional[str],
) -> Dict[str, Any]:
    input_title = (title or "").strip()
    input_artist = (artist or "").strip()

    result = {
        "case_name": case_name,
        "input_title": input_title,
        "input_artist": input_artist,
        "queries": [],
        "fallback_used": False,
        "scored_candidates": [],
        "chosen_candidate": None,
        "best_candidate": None,
        "unmatched_reason": "empty_search_terms",
        "search_title": input_title,
        "search_artist": input_artist,
    }

    if not input_title:
        return result

    queries = _build_case_queries(input_title, input_artist)
    result["queries"] = [query["query"] for query in queries]

    raw_tracks: List[Dict[str, Any]] = []
    track_sources: Dict[Tuple[Any, ...], Dict[str, str]] = {}

    for index, strategy in enumerate(queries):
        if strategy["mode"] == "track_artist":
            fetched_tracks = search_track(
                access_token=access_token,
                title=strategy["title"],
                artist=strategy["artist"] or None,
                market=market,
                limit=SEARCH_LIMIT,
            )
        elif strategy["mode"] == "track_only":
            fetched_tracks = search_track(
                access_token=access_token,
                title=strategy["title"],
                artist=None,
                market=market,
                limit=SEARCH_LIMIT,
            )
        else:
            fetched_tracks = search_tracks_query(
                access_token=access_token,
                query=strategy["query"],
                market=market,
                limit=SEARCH_LIMIT,
            )

        if index > 0 and fetched_tracks:
            result["fallback_used"] = True

        for track in fetched_tracks:
            track_key = _track_dedupe_key(track)
            if track_key not in track_sources:
                track_sources[track_key] = {
                    "search_title": strategy["title"] or input_title,
                    "search_artist": strategy["artist"] or input_artist,
                    "query_type": "primary" if index == 0 else "fallback",
                    "query_used": strategy["query"],
                }
            raw_tracks.append(track)

        if not raw_tracks:
            continue

        scored_candidates = _score_tracks(
            raw_tracks,
            track_sources,
            input_title=input_title,
            input_artist=input_artist,
            chosen_case=case_name,
        )
        result["scored_candidates"] = scored_candidates
        result["chosen_candidate"] = _pick_best_acceptable_candidate(
            scored_candidates,
            has_artist=bool(input_artist),
            input_artist=input_artist,
        )
        result["best_candidate"] = dict(result["chosen_candidate"] or scored_candidates[0])
        result["best_candidate"]["top_candidates"] = scored_candidates[:3]
        result["unmatched_reason"] = _build_unmatched_reason(
            scored_candidates,
            has_artist=bool(input_artist),
            input_artist=input_artist,
        )
        result["search_title"] = result["best_candidate"].get("search_title", input_title)
        result["search_artist"] = result["best_candidate"].get("search_artist", input_artist)

        print(
            f"[spotify-match:candidates] input='{input_artist} - {input_title}' "
            f"query='{strategy['query']}' candidates=["
            + "; ".join(_candidate_score_log(candidate) for candidate in scored_candidates[:SEARCH_LIMIT])
            + "]"
        )

        chosen_candidate = result["chosen_candidate"]
        if chosen_candidate and float(chosen_candidate.get("score", 0.0)) >= EARLY_RETURN_SCORE:
            break

    return result


def _extract_case_inputs(
    title: str,
    artist: str,
    song_meta: Dict[str, Any],
) -> List[Dict[str, str]]:
    """
    Do not evaluate original+swapped again in Spotify matching.
    Parser owns orientation. Matching owns candidate scoring/classification.
    This keeps Spotify API calls from doubling.
    """
    return [
        {
            "case_name": str(song_meta.get("chosen_case") or "original"),
            "artist": artist or "",
            "title": title or "",
        }
    ]

def _case_score(case_result: Dict[str, Any]) -> float:
    candidate = case_result.get("chosen_candidate") or case_result.get("best_candidate") or {}
    return float(candidate.get("score", 0.0))


def _case_popularity(case_result: Dict[str, Any]) -> int:
    candidate = case_result.get("chosen_candidate") or case_result.get("best_candidate") or {}
    return int(candidate.get("popularity", 0))


def _choose_case_result(
    case_results: List[Dict[str, Any]],
    *,
    swap_guard_applied: bool,
    swap_guard_reason: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    accepted = [case_result for case_result in case_results if case_result.get("chosen_candidate")]
    if accepted:
        original_result = next((item for item in accepted if item["case_name"] == "original"), None)
        swapped_result = next((item for item in accepted if item["case_name"] == "swapped"), None)

        if original_result and swapped_result and swap_guard_applied:
            if _case_score(swapped_result) <= _case_score(original_result) + SWAP_GUARD_MARGIN:
                return original_result, swap_guard_reason or "swap_guard_preferred_original"

        selected = max(
            accepted,
            key=lambda item: (_case_score(item), _case_popularity(item)),
        )
        return selected, f"{selected['case_name']}_case_higher_score"

    available = [case_result for case_result in case_results if case_result.get("best_candidate")]
    if not available:
        return None, "no_search_result"

    selected = max(
        available,
        key=lambda item: (_case_score(item), _case_popularity(item)),
    )
    return selected, selected.get("unmatched_reason", "no_acceptable_candidates")


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
    song_meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    input_title = (title or "").strip()
    input_artist = (artist or "").strip()
    cache_key = build_match_cache_key(input_title, input_artist)
    song_meta = song_meta or {}
    swap_guard_applied = bool(song_meta.get("swap_guard_applied", False))
    swap_guard_reason = str(song_meta.get("swap_guard_reason") or "")

    if cache_key in _MATCH_CACHE:
        cached = _MATCH_CACHE[cache_key]
        cached_debug = _MATCH_DEBUG.get(cache_key, {})
        selected = "none"
        candidate_count = 0
        early_return = False
        chosen_case = str(cached_debug.get("selected_case") or song_meta.get("chosen_case") or "original")
        if cached:
            selected = f"{cached.get('name', '')} / {', '.join(cached.get('artists', []))}"
            candidate_count = len(cached.get("top_candidates", []))
            early_return = float(cached.get("score", 0.0)) >= EARLY_RETURN_SCORE

        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            cache_status="hit",
            chosen_case=chosen_case,
            queries=list(cached_debug.get("queries", [])),
            fallback_used=bool(cached_debug.get("fallback_used", False)),
            candidate_count=candidate_count,
            selected=selected,
            selected_score=float(cached.get("score", 0.0)) if cached else 0.0,
            reason=str(cached.get("reason", "")) if cached else "",
            unmatched_reason="" if cached else str(cached_debug.get("unmatched_reason", "")),
            early_return=early_return,
        )
        return cached

    case_inputs = _extract_case_inputs(input_title, input_artist, song_meta)
    case_results = [
        _evaluate_case(
            access_token,
            case_name=case_input["case_name"],
            title=case_input["title"],
            artist=case_input["artist"],
            market=market,
        )
        for case_input in case_inputs
    ]

    selected_case_result, decision_reason = _choose_case_result(
        case_results,
        swap_guard_applied=swap_guard_applied,
        swap_guard_reason=swap_guard_reason,
    )

    if not selected_case_result:
        _store_match_debug(
            cache_key,
            selected_case=str(song_meta.get("chosen_case") or "original"),
            search_title=input_title,
            search_artist=input_artist,
            unmatched_reason="no_search_result",
            top_candidates=[],
            case_results=case_results,
        )
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            cache_status="miss",
            chosen_case=str(song_meta.get("chosen_case") or "original"),
            queries=[],
            fallback_used=False,
            candidate_count=0,
            selected="none",
            selected_score=0.0,
            reason=decision_reason,
            unmatched_reason="no_search_result",
            early_return=False,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    best_candidate = selected_case_result.get("best_candidate") or {}
    chosen_candidate = selected_case_result.get("chosen_candidate")
    selected_case = selected_case_result["case_name"]
    selected_queries = list(selected_case_result.get("queries", []))
    fallback_used = bool(selected_case_result.get("fallback_used", False))
    candidate_count = len(selected_case_result.get("scored_candidates", []))

    if not chosen_candidate:
        unmatched_reason = selected_case_result.get("unmatched_reason", "no_acceptable_candidates")
        _store_match_debug(
            cache_key,
            selected_case=selected_case,
            search_title=selected_case_result.get("search_title", input_title),
            search_artist=selected_case_result.get("search_artist", input_artist),
            unmatched_reason=unmatched_reason,
            top_candidates=selected_case_result.get("scored_candidates", []),
            case_results=case_results,
        )
        _MATCH_CACHE[cache_key] = None
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            cache_status="miss",
            chosen_case=selected_case,
            queries=selected_queries,
            fallback_used=fallback_used,
            candidate_count=candidate_count,
            selected=f"{best_candidate.get('name', '')} / {', '.join(best_candidate.get('artists', []))}",
            selected_score=float(best_candidate.get("score", 0.0)),
            reason=decision_reason,
            unmatched_reason=unmatched_reason,
            early_return=False,
        )
        return None

    best = dict(chosen_candidate)
    best["top_candidates"] = selected_case_result.get("scored_candidates", [])[:3]
    best["chosen_case"] = selected_case
    best["reason"] = decision_reason
    best["search_queries"] = selected_queries
    best["parse_reason"] = str(song_meta.get("reason") or "")

    unmatched_reason = ""
    early_return = float(best.get("score", 0.0)) >= EARLY_RETURN_SCORE
    selected_name = f"{best.get('name', '')} / {', '.join(best.get('artists', []))}"

    _store_match_debug(
        cache_key,
        selected_case=selected_case,
        search_title=best.get("search_title", input_title),
        search_artist=best.get("search_artist", input_artist),
        unmatched_reason=unmatched_reason,
        top_candidates=selected_case_result.get("scored_candidates", []),
        case_results=case_results,
    )

    _MATCH_DEBUG[cache_key]["queries"] = selected_queries
    _MATCH_DEBUG[cache_key]["fallback_used"] = fallback_used

    _log_match(
        input_title=input_title,
        input_artist=input_artist,
        cache_status="miss",
        chosen_case=selected_case,
        queries=selected_queries,
        fallback_used=fallback_used,
        candidate_count=candidate_count,
        selected=selected_name,
        selected_score=float(best.get("score", 0.0)),
        reason=decision_reason,
        unmatched_reason=unmatched_reason,
        early_return=early_return,
    )

    if len(_MATCH_CACHE) >= MAX_CACHE_SIZE:
        _MATCH_CACHE.clear()
        _MATCH_DEBUG.clear()
    _MATCH_CACHE[cache_key] = best
    return best
