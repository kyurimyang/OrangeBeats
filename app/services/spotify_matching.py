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
MAX_CACHE_SIZE = 300
SEARCH_LIMIT = 7
STRICT_TITLE_VARIANT_LIMIT = 2
STRICT_ARTIST_VARIANT_LIMIT = 3
BROAD_TITLE_VARIANT_LIMIT = 3


def _candidate_to_result(
    track: Dict[str, Any],
    score: float,
    detail: Dict[str, float],
    *,
    search_title: str,
    search_artist: str,
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
        "orientation": "title_artist",
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
    normalized_artist: str,
    title_variants: List[str],
    query1: str,
    fallback_used: bool,
    cache_status: str,
    candidate_count: int,
    selected: str,
    selected_score: float,
    unmatched_reason: str,
    early_return: bool,
    rerank_executed: bool,
    swap_decision: str,
    global_direction: str,
) -> None:
    extra = f" unmatched_reason='{unmatched_reason}'" if unmatched_reason else ""
    print(
        f"[spotify-match] input='{input_artist} - {input_title}' "
        f"normalized_artist='{normalized_artist}' title_variants={title_variants} "
        f"query1='{query1}' fallback_used={str(fallback_used).lower()} "
        f"cache={cache_status} candidates={candidate_count} "
        f"selected='{selected}' score={selected_score:.4f}{extra} early_return={str(early_return).lower()} "
        f"rerank={str(rerank_executed).lower()} swap={swap_decision} "
        f"global_direction={global_direction}"
    )


def _track_dedupe_key(track: Dict[str, Any]) -> Tuple[Any, ...]:
    artists = tuple((artist or {}).get("name", "") for artist in track.get("artists", []))
    return (
        track.get("id") or "",
        track.get("uri") or "",
        track.get("name", ""),
        artists,
    )


def _build_search_strategies(
    title_variants: List[str],
    artist_variants: List[str],
) -> List[Dict[str, str]]:
    strategies: List[Dict[str, str]] = []
    seen = set()

    def add_strategy(mode: str, *, title: str = "", artist: str = "", query: str = "") -> None:
        key = (mode, title.strip(), artist.strip(), query.strip())
        if key in seen:
            return
        seen.add(key)
        strategies.append(
            {
                "mode": mode,
                "title": title.strip(),
                "artist": artist.strip(),
                "query": query.strip(),
            }
        )

    strict_titles = [variant for variant in title_variants[:STRICT_TITLE_VARIANT_LIMIT] if variant]
    strict_artists = [variant for variant in artist_variants[:STRICT_ARTIST_VARIANT_LIMIT] if variant]

    if strict_artists:
        for title in strict_titles:
            for artist in strict_artists:
                add_strategy("track_artist", title=title, artist=artist)

        for title in strict_titles:
            for artist in strict_artists[:2]:
                add_strategy("query", title=title, artist=artist, query=f"{title} {artist}")

    for title in title_variants[:BROAD_TITLE_VARIANT_LIMIT]:
        add_strategy("track_only", title=title)

    return strategies


def _score_tracks(
    raw_tracks: List[Dict[str, Any]],
    track_sources: Dict[Tuple[Any, ...], Dict[str, str]],
    *,
    input_title: str,
    input_artist: str,
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


def _candidate_is_acceptable(candidate: Dict[str, Any], *, has_artist: bool) -> bool:
    detail = candidate.get("score_detail", {})
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    score = float(candidate.get("score", 0.0))

    if score >= DIRECT_ACCEPT_SCORE:
        return True
    if score < MIN_ACCEPT_SCORE:
        return False
    if title_score < MIN_TITLE_SCORE:
        return False
    if has_artist and artist_score < MIN_ARTIST_SCORE:
        return False
    return True


def _pick_best_acceptable_candidate(
    scored_candidates: List[Dict[str, Any]],
    *,
    has_artist: bool,
) -> Optional[Dict[str, Any]]:
    acceptable = [
        candidate for candidate in scored_candidates
        if _candidate_is_acceptable(candidate, has_artist=has_artist)
    ]
    if not acceptable:
        return None
    return max(
        acceptable,
        key=lambda item: (
            item.get("popularity", 0),
            item["score"],
            item["score_detail"].get("title_score", 0.0),
            item["score_detail"].get("artist_score", 0.0),
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
    detail = best.get("score_detail", {})
    title_score = float(detail.get("title_score", 0.0))
    artist_score = float(detail.get("artist_score", 0.0))
    score = float(best.get("score", 0.0))

    if title_score < MIN_TITLE_SCORE:
        return f"title_mismatch(score={score:.2f},title={title_score:.2f})"
    if has_artist and artist_score < MIN_ARTIST_SCORE:
        return f"artist_mismatch(score={score:.2f},artist={artist_score:.2f})"
    return f"low_score({score:.2f})"


def _store_match_debug(
    cache_key: Tuple[str, str],
    *,
    search_title: str,
    search_artist: str,
    unmatched_reason: str,
    top_candidates: List[Dict[str, Any]],
) -> None:
    _MATCH_DEBUG[cache_key] = {
        "search_title": search_title,
        "search_artist": search_artist,
        "unmatched_reason": unmatched_reason,
        "top_candidates": [
            {
                "name": candidate.get("name", ""),
                "artists": candidate.get("artists", []),
                "score": candidate.get("score", 0.0),
                "popularity": candidate.get("popularity", 0),
                "score_detail": candidate.get("score_detail", {}),
            }
            for candidate in top_candidates[:3]
        ],
    }


def get_match_debug(title: str, artist: str) -> Dict[str, Any]:
    cache_key = build_match_cache_key(title, artist)
    return dict(_MATCH_DEBUG.get(cache_key, {}))


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
    swap_decision = "true" if song_meta.get("swap_applied") else "false"
    global_direction = str(song_meta.get("global_direction") or "unknown")
    title_variants = build_title_search_variants(input_title)
    raw_query_title = title_variants[0] if title_variants else input_title
    normalized_artist = resolve_artist_alias(input_artist)
    artist_variants = build_artist_search_variants(input_artist)
    query1 = f'track:"{raw_query_title}" artist:"{normalized_artist}"'

    if cache_key in _MATCH_CACHE:
        cached = _MATCH_CACHE[cache_key]
        cached_debug = _MATCH_DEBUG.get(cache_key, {})
        selected = "none"
        candidate_count = 0
        early_return = False
        if cached:
            selected = f"{cached.get('name', '')} / {', '.join(cached.get('artists', []))}"
            candidate_count = len(cached.get("top_candidates", []))
            early_return = cached.get("score", 0.0) >= EARLY_RETURN_SCORE
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=False,
            cache_status="hit",
            candidate_count=candidate_count,
            selected=selected,
            selected_score=float(cached.get("score", 0.0)) if cached else 0.0,
            unmatched_reason="" if cached else str(cached_debug.get("unmatched_reason", "")),
            early_return=early_return,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        return cached

    if not raw_query_title:
        _store_match_debug(
            cache_key,
            search_title=input_title,
            search_artist=input_artist,
            unmatched_reason="empty_search_terms",
            top_candidates=[],
        )
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=False,
            cache_status="miss",
            candidate_count=0,
            selected="none",
            selected_score=0.0,
            unmatched_reason="empty_search_terms",
            early_return=False,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    search_strategies = _build_search_strategies(title_variants, artist_variants)
    raw_tracks: List[Dict[str, Any]] = []
    track_sources: Dict[Tuple[Any, ...], Dict[str, str]] = {}
    scored_candidates: List[Dict[str, Any]] = []
    fallback_used = False

    for index, strategy in enumerate(search_strategies):
        strategy_mode = strategy.get("mode", "")
        strategy_title = strategy.get("title", "")
        strategy_artist = strategy.get("artist", "")
        strategy_query = strategy.get("query", "")

        if strategy_mode == "track_artist":
            fetched_tracks = search_track(
                access_token=access_token,
                title=strategy_title,
                artist=strategy_artist or None,
                market=market,
                limit=SEARCH_LIMIT,
            )
        elif strategy_mode == "track_only":
            fetched_tracks = search_track(
                access_token=access_token,
                title=strategy_title,
                artist=None,
                market=market,
                limit=SEARCH_LIMIT,
            )
        else:
            fetched_tracks = search_tracks_query(
                access_token=access_token,
                query=strategy_query,
                market=market,
                limit=SEARCH_LIMIT,
            )

        if index > 0 and fetched_tracks:
            fallback_used = True

        for track in fetched_tracks:
            track_key = _track_dedupe_key(track)
            if track_key not in track_sources:
                track_sources[track_key] = {
                    "search_title": strategy_title or input_title,
                    "search_artist": strategy_artist or input_artist,
                }
            raw_tracks.append(track)

        if not raw_tracks:
            continue

        scored_candidates = _score_tracks(
            raw_tracks,
            track_sources,
            input_title=input_title,
            input_artist=input_artist,
        )
        chosen_candidate = _pick_best_acceptable_candidate(
            scored_candidates,
            has_artist=bool(input_artist),
        )
        if chosen_candidate and float(chosen_candidate.get("score", 0.0)) >= EARLY_RETURN_SCORE:
            break

    if not scored_candidates:
        _store_match_debug(
            cache_key,
            search_title=input_title,
            search_artist=input_artist,
            unmatched_reason="no_candidates",
            top_candidates=[],
        )
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=fallback_used,
            cache_status="miss",
            candidate_count=0,
            selected="none",
            selected_score=0.0,
            unmatched_reason="no_candidates",
            early_return=False,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    chosen_candidate = _pick_best_acceptable_candidate(
        scored_candidates,
        has_artist=bool(input_artist),
    )
    best = dict(chosen_candidate or scored_candidates[0])
    best["top_candidates"] = scored_candidates[:3]
    early_return = best["score"] >= EARLY_RETURN_SCORE
    selected = f"{best.get('name', '')} / {', '.join(best.get('artists', []))}"
    unmatched_reason = "" if chosen_candidate else _build_unmatched_reason(
        scored_candidates,
        has_artist=bool(input_artist),
    )
    _store_match_debug(
        cache_key,
        search_title=best.get("search_title", input_title),
        search_artist=best.get("search_artist", input_artist),
        unmatched_reason=unmatched_reason,
        top_candidates=scored_candidates,
    )

    _log_match(
        input_title=input_title,
        input_artist=input_artist,
        normalized_artist=normalized_artist,
        title_variants=title_variants,
        query1=query1,
        fallback_used=fallback_used,
        cache_status="miss",
        candidate_count=len(scored_candidates),
        selected=selected,
        selected_score=best["score"],
        unmatched_reason=unmatched_reason,
        early_return=early_return,
        rerank_executed=False,
        swap_decision=swap_decision,
        global_direction=global_direction,
    )

    if not chosen_candidate:
        _MATCH_CACHE[cache_key] = None
        return None

    if len(_MATCH_CACHE) >= MAX_CACHE_SIZE:
        _MATCH_CACHE.clear()
        _MATCH_DEBUG.clear()
    _MATCH_CACHE[cache_key] = best
    return best
