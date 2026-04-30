import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    build_artist_search_variants,
    build_match_cache_key,
    build_title_search_variants,
    compute_match_score,
    _possible_artist_romanization_match,
    resolve_artist_alias,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
_MATCH_DEBUG: Dict[Tuple[str, str], Dict[str, Any]] = {}

EARLY_RETURN_SCORE = 0.90
DIRECT_ACCEPT_SCORE = 0.85
MIN_ACCEPT_SCORE = 0.85
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
REVIEW_NEEDED_SCORE = 0.50

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
    "instrumental",
    "inst",
    "tribute",
    "lullaby",
    "nightcore",
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
    "title_matched_artist_alias_candidate": "제목은 일치하지만 가수명이 Spotify에서 다른 표기로 등록되어 확인이 필요합니다.",
    "artist_matched_title_mismatch": "가수는 일치하지만 제목이 다른 표기로 등록되어 확인이 필요합니다.",
    "artist_matched_title_alias_candidate": "가수는 일치하지만 제목이 다른 언어/표기로 등록된 후보일 수 있습니다.",
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
    version_penalty = float(detail.get("version_penalty", 0.0))
    haystack = _candidate_text(candidate_title, candidate_artists)
    tags: List[str] = []

    if title_score >= 0.95 and (not input_artist or artist_score >= 0.85):
        tags.append("exact_match_pattern")

    if (
        bool(detail.get("artist_alias_matched"))
        or bool(detail.get("title_alias_matched"))
        or bool(detail.get("title_variant_matched"))
        or title_score >= 0.90
        or artist_score >= 0.90
    ):
        tags.append("notation_difference_pattern")

    if version_penalty > 0 or _contains_keyword(haystack, ACCEPTABLE_VERSION_KEYWORDS):
        tags.append("acceptable_version_pattern")

    if _contains_keyword(haystack, NON_ORIGINAL_KEYWORDS):
        tags.append("non_original_audio_pattern")

    if input_artist and artist_score >= 0.85 and title_score < 0.55:
        tags.append("artist_only_overconfidence_pattern")

    if input_artist and title_score >= 0.85 and artist_score < MIN_ARTIST_SCORE:
        tags.append("title_only_overconfidence_pattern")

    if _is_short_title_false_positive(input_title, candidate_title, title_score):
        tags.append("short_title_false_positive_pattern")

    if title_score < 0.40 and (not input_artist or artist_score < 0.40):
        tags.append("weak_both_pattern")

    if api_rank == 0 and (title_score >= 0.95 or artist_score >= 0.95):
        tags.append("top_rank_one_side_exact_pattern")

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
    bonuses: Dict[str, float] = {}
    penalties: Dict[str, float] = {}
    caps: Dict[str, float] = {}

    if "exact_match_pattern" in pattern_tags:
        bonuses["exact_match_pattern"] = 0.03
        adjusted += 0.03

    if "notation_difference_pattern" in pattern_tags:
        bonuses["notation_difference_pattern"] = 0.03
        adjusted += 0.03
        if title_score >= 0.98 and artist_score < MIN_ARTIST_SCORE:
            adjusted = max(adjusted, 0.78)
            bonuses["title_exact_artist_spelling_gap_floor"] = round(max(0.0, 0.78 - base_score), 4)
        if artist_score >= 0.98 and title_score < MIN_TITLE_SCORE:
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
        and (title_score >= 0.98 or artist_score >= 0.98)
    )

    if "artist_only_overconfidence_pattern" in pattern_tags and not one_side_exact_spelling_gap:
        caps["artist_only_overconfidence_pattern"] = 0.69

    if "title_only_overconfidence_pattern" in pattern_tags and not one_side_exact_spelling_gap:
        penalties["title_only_overconfidence_pattern"] = 0.12
        adjusted -= 0.12
        caps["title_only_overconfidence_pattern"] = 0.78

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


def decide_match_status(score: float) -> str:
    return _status_from_score(score)


def rank_candidates(scored_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        scored_candidates,
        key=lambda item: (
            item["score"],
            item.get("popularity", 0),
            item["score_detail"].get("title_score", 0.0),
            item["score_detail"].get("artist_score", 0.0),
        ),
        reverse=True,
    )


def _candidate_reason(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> str:
    detail = candidate.get("score_detail", {})
    pattern_tags = set(detail.get("pattern_tags", []))
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    version_penalty = float(detail.get("version_penalty", 0.0))
    score = float(candidate.get("score", 0.0))
    artist_alias_matched = bool(detail.get("artist_alias_matched", False))

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
        detail["api_rank"] = api_rank + 1
        detail["score_before_context"] = round(base_score, 4)
        source = track_sources.get(_track_dedupe_key(track), {})
        candidate = _candidate_to_result(
                track,
                score,
                detail,
                search_title=source.get("search_title", input_title),
                search_artist=source.get("search_artist", input_artist),
                chosen_case=chosen_case,
            )
        candidate["candidate_rank"] = len(scored_candidates)
        scored_candidates.append(candidate)

    return rank_candidates(scored_candidates)


def _classify_candidate(candidate: Dict[str, Any], *, has_artist: bool, input_artist: str = "") -> str:
    """Classify a Spotify candidate without making extra searches."""
    score = float(candidate.get("score", 0.0))
    return _status_from_score(score)


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
