from typing import Any, Dict, List, Optional, Tuple

from app.constants.pipeline_params import SPOTIFY_MID_CONF
from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    build_title_variants,
    build_match_cache_key,
    compute_match_score,
    resolve_artist_alias,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

EARLY_RETURN_SCORE = 0.90
MIN_ACCEPT_SCORE = 0.75
MAX_CACHE_SIZE = 300
LOW_CONF_FALLBACK_SCORE = 0.45


def _candidate_to_result(
    track: Dict[str, Any],
    score: float,
    detail: Dict[str, float],
    *,
    search_title: str,
    search_artist: str,
) -> Dict[str, Any]:
    return {
        'id': track.get('id'),
        'uri': track.get('uri'),
        'name': track.get('name', ''),
        'artists': [a.get('name', '') for a in track.get('artists', [])],
        'album': (track.get('album') or {}).get('name', ''),
        'score': score,
        'score_detail': detail,
        'orientation': 'title_artist',
        'llm_reranked': False,
        'llm_confidence': '',
        'llm_reason': '',
        'search_title': search_title,
        'search_artist': search_artist,
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
    extra = f" unmatched_reason='{unmatched_reason}'" if unmatched_reason else ''
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
    artists = tuple((artist or {}).get('name', '') for artist in track.get('artists', []))
    return (
        track.get('id') or '',
        track.get('uri') or '',
        track.get('name', ''),
        artists,
    )


def _score_tracks(
    raw_tracks: List[Dict[str, Any]],
    *,
    input_title: str,
    normalized_artist: str,
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
        score, detail = compute_match_score(input_title, normalized_artist, track)
        scored_candidates.append(
            _candidate_to_result(
                track,
                score,
                detail,
                search_title=input_title,
                search_artist=normalized_artist,
            )
        )
    scored_candidates.sort(key=lambda item: item['score'], reverse=True)
    return scored_candidates


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
    song_meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    input_title = (title or '').strip()
    input_artist = (artist or '').strip()
    cache_key = build_match_cache_key(input_title, input_artist)
    song_meta = song_meta or {}
    swap_decision = 'true' if song_meta.get('swap_applied') else 'false'
    global_direction = str(song_meta.get('global_direction') or 'unknown')
    title_variants = build_title_variants(input_title)
    raw_query_title = title_variants[0] if title_variants else input_title
    normalized_artist = resolve_artist_alias(input_artist)
    query1 = f'track:"{raw_query_title}" artist:"{normalized_artist}"'

    if cache_key in _MATCH_CACHE:
        cached = _MATCH_CACHE[cache_key]
        selected = 'none'
        candidate_count = 0
        early_return = False
        if cached:
            selected = f"{cached.get('name', '')} / {', '.join(cached.get('artists', []))}"
            candidate_count = len(cached.get('top_candidates', []))
            early_return = cached.get('score', 0.0) >= EARLY_RETURN_SCORE
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=False,
            cache_status='hit',
            candidate_count=candidate_count,
            selected=selected,
            selected_score=float(cached.get('score', 0.0)) if cached else 0.0,
            unmatched_reason='',
            early_return=early_return,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        return cached

    if not raw_query_title or not normalized_artist:
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=False,
            cache_status='miss',
            candidate_count=0,
            selected='none',
            selected_score=0.0,
            unmatched_reason='empty_search_terms',
            early_return=False,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    raw_tracks = search_track(
        access_token=access_token,
        title=raw_query_title,
        artist=normalized_artist,
        market=market,
        limit=3,
    )
    scored_candidates = _score_tracks(
        raw_tracks,
        input_title=input_title,
        normalized_artist=normalized_artist,
    )
    fallback_used = False

    fallback_title = next((variant for variant in title_variants[1:] if variant and variant != raw_query_title), '')
    should_use_fallback = (not scored_candidates) or (scored_candidates[0]['score'] < LOW_CONF_FALLBACK_SCORE)
    if should_use_fallback and fallback_title:
        fallback_query = f'{fallback_title} {normalized_artist}'.strip()
        primary_query_words = f'{raw_query_title} {normalized_artist}'.strip()
        if fallback_query and fallback_query.lower() != primary_query_words.lower():
            fallback_used = True
            fallback_tracks = search_tracks_query(
                access_token=access_token,
                query=fallback_query,
                market=market,
                limit=3,
            )
            if fallback_tracks:
                scored_candidates = _score_tracks(
                    raw_tracks + fallback_tracks,
                    input_title=input_title,
                    normalized_artist=normalized_artist,
                )

    if not scored_candidates:
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            normalized_artist=normalized_artist,
            title_variants=title_variants,
            query1=query1,
            fallback_used=fallback_used,
            cache_status='miss',
            candidate_count=0,
            selected='none',
            selected_score=0.0,
            unmatched_reason='no_candidates',
            early_return=False,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    best = dict(scored_candidates[0])
    best['top_candidates'] = scored_candidates[:3]
    early_return = best['score'] >= EARLY_RETURN_SCORE
    selected = f"{best.get('name', '')} / {', '.join(best.get('artists', []))}"

    _log_match(
        input_title=input_title,
        input_artist=input_artist,
        normalized_artist=normalized_artist,
        title_variants=title_variants,
        query1=query1,
        fallback_used=fallback_used,
        cache_status='miss',
        candidate_count=len(scored_candidates),
        selected=selected,
        selected_score=best['score'],
        unmatched_reason='' if best['score'] >= max(SPOTIFY_MID_CONF, MIN_ACCEPT_SCORE) else f"low_score({best['score']:.2f})",
        early_return=early_return,
        rerank_executed=False,
        swap_decision=swap_decision,
        global_direction=global_direction,
    )

    if best['score'] < max(SPOTIFY_MID_CONF, MIN_ACCEPT_SCORE):
        _MATCH_CACHE[cache_key] = None
        return None

    if len(_MATCH_CACHE) >= MAX_CACHE_SIZE:
        _MATCH_CACHE.clear()
    _MATCH_CACHE[cache_key] = best
    return best
