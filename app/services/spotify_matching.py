from typing import Any, Dict, List, Optional, Tuple

from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    build_artist_search_variants,
    build_match_cache_key,
    build_title_search_variants,
    compute_match_score,
    resolve_artist_alias,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
_MATCH_DEBUG: Dict[Tuple[str, str], Dict[str, Any]] = {}

EARLY_RETURN_SCORE = 0.90
DIRECT_ACCEPT_SCORE = 0.84
MIN_ACCEPT_SCORE = 0.72
MIN_TITLE_SCORE = 0.90
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
PARTIAL_CONFIDENCE_SCORE = 0.30


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
    for track in unique_tracks:
        score, detail = compute_match_score(input_title, input_artist, track)
        source = track_sources.get(_track_dedupe_key(track), {})
        scored_candidates.append(
            _candidate_to_result(
                track,
                score,
                detail,
                search_title=source.get("search_title", input_title),
                search_artist=source.get("search_artist", input_artist),
                chosen_case=chosen_case,
            )
        )

    scored_candidates.sort(
        key=lambda item: (
            item["score"],
            item.get("popularity", 0),
            item["score_detail"].get("title_score", 0.0),
            item["score_detail"].get("artist_score", 0.0),
        ),
        reverse=True,
    )
    return scored_candidates


def _classify_candidate(candidate: Dict[str, Any], *, has_artist: bool) -> str:
    """Classify a Spotify candidate without making extra searches."""
    detail = candidate.get("score_detail", {})
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    score = float(candidate.get("score", 0.0))

    # Safe auto-add cases.
    if score >= DIRECT_ACCEPT_SCORE:
        return "matched"
    if has_artist and artist_score >= EXACT_ARTIST_SCORE and title_score >= EXACT_ARTIST_MIN_TITLE_SCORE:
        return "matched"
    if score >= MIN_ACCEPT_SCORE and title_score >= MIN_TITLE_SCORE and (not has_artist or artist_score >= MIN_ARTIST_SCORE):
        return "matched"

    # Useful review candidates. Do not auto-add these to the playlist.
    if has_artist and title_score >= ARTIST_ALIAS_CANDIDATE_TITLE_SCORE and artist_score < MIN_ARTIST_SCORE:
        return "artist_alias_candidate"
    if has_artist and artist_score >= TITLE_ALIAS_CANDIDATE_ARTIST_SCORE and title_score < MIN_TITLE_SCORE:
        return "title_alias_candidate"
    if score >= PARTIAL_CONFIDENCE_SCORE or title_score >= 0.70 or (has_artist and artist_score >= 0.70):
        return "low_confidence"
    return "unmatched"


def _candidate_is_acceptable(candidate: Dict[str, Any], *, has_artist: bool) -> bool:
    return _classify_candidate(candidate, has_artist=has_artist) == "matched"


def _candidate_is_recoverable(candidate: Dict[str, Any], *, has_artist: bool) -> bool:
    return _classify_candidate(candidate, has_artist=has_artist) in {
        "artist_alias_candidate",
        "title_alias_candidate",
        "low_confidence",
    }


def _attach_candidate_status(candidate: Dict[str, Any], *, has_artist: bool) -> Dict[str, Any]:
    enriched = dict(candidate)
    status = _classify_candidate(candidate, has_artist=has_artist)
    enriched["match_status"] = status
    if status == "artist_alias_candidate":
        enriched["low_confidence_reason"] = "title_matched_artist_alias_candidate"
    elif status == "title_alias_candidate":
        enriched["low_confidence_reason"] = "artist_matched_title_alias_candidate"
    elif status == "low_confidence":
        enriched["low_confidence_reason"] = "partial_match_needs_review"
    return enriched


def _pick_best_acceptable_candidate(
    scored_candidates: List[Dict[str, Any]],
    *,
    has_artist: bool,
) -> Optional[Dict[str, Any]]:
    matched = [
        _attach_candidate_status(candidate, has_artist=has_artist)
        for candidate in scored_candidates
        if _candidate_is_acceptable(candidate, has_artist=has_artist)
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
        _attach_candidate_status(candidate, has_artist=has_artist)
        for candidate in scored_candidates
        if _candidate_is_recoverable(candidate, has_artist=has_artist)
    ]
    if not recoverable:
        return None

    status_priority = {
        "artist_alias_candidate": 3,
        "title_alias_candidate": 3,
        "low_confidence": 2,
        "unmatched": 0,
    }
    return max(
        recoverable,
        key=lambda item: (
            status_priority.get(item.get("match_status", "unmatched"), 0),
            item["score_detail"].get("title_score", 0.0),
            item["score_detail"].get("artist_score", 0.0),
            item["score"],
            item.get("popularity", 0),
        ),
    )

def _build_unmatched_reason(
    scored_candidates: List[Dict[str, Any]],
    *,
    has_artist: bool,
) -> str:
    if not scored_candidates:
        return "no_candidates"

    best = scored_candidates[0]
    status = _classify_candidate(best, has_artist=has_artist)
    detail = best.get("score_detail", {})
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    score = float(best.get("score", 0.0))

    if status == "matched":
        return ""
    if status == "artist_alias_candidate":
        return f"artist_alias_candidate(score={score:.2f},title={title_score:.2f},artist={artist_score:.2f})"
    if status == "title_alias_candidate":
        return f"title_alias_candidate(score={score:.2f},title={title_score:.2f},artist={artist_score:.2f})"
    if status == "low_confidence":
        return f"low_confidence(score={score:.2f},title={title_score:.2f},artist={artist_score:.2f})"
    if title_score < MIN_TITLE_SCORE:
        return f"title_mismatch(score={score:.2f},title={title_score:.2f})"
    if has_artist and artist_score < MIN_ARTIST_SCORE:
        return f"artist_mismatch(score={score:.2f},artist={artist_score:.2f})"
    return f"low_score({score:.2f})"

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
        )
        result["best_candidate"] = dict(result["chosen_candidate"] or scored_candidates[0])
        result["best_candidate"]["top_candidates"] = scored_candidates[:3]
        result["unmatched_reason"] = _build_unmatched_reason(
            scored_candidates,
            has_artist=bool(input_artist),
        )
        result["search_title"] = result["best_candidate"].get("search_title", input_title)
        result["search_artist"] = result["best_candidate"].get("search_artist", input_artist)

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
        return None, "no_candidates"

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
            unmatched_reason="no_candidates",
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
            unmatched_reason="no_candidates",
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
