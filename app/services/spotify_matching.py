from typing import Any, Dict, List, Optional, Tuple

from app.constants.pipeline_params import SPOTIFY_MID_CONF
from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    _clean_artist_name_for_search,
    _clean_track_title_for_search,
    build_match_cache_key,
    compute_match_score,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

EARLY_RETURN_SCORE = 0.90
MIN_ACCEPT_SCORE = 0.75
MAX_CACHE_SIZE = 300


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
    query: str,
    cache_status: str,
    candidate_count: int,
    selected: str,
    early_return: bool,
    rerank_executed: bool,
    swap_decision: str,
    global_direction: str,
) -> None:
    print(
        f"[spotify-match] input='{input_artist} - {input_title}' "
        f"query='{query}' cache={cache_status} candidates={candidate_count} "
        f"selected='{selected}' early_return={str(early_return).lower()} "
        f"rerank={str(rerank_executed).lower()} swap={swap_decision} "
        f"global_direction={global_direction}"
    )


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
            query='-',
            cache_status='hit',
            candidate_count=candidate_count,
            selected=selected,
            early_return=early_return,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        return cached

    search_title = _clean_track_title_for_search(input_title)
    search_artist = _clean_artist_name_for_search(input_artist)
    query = f'track:"{search_title}" artist:"{search_artist}"'

    if not search_title or not search_artist:
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            query=query,
            cache_status='miss',
            candidate_count=0,
            selected='none',
            early_return=False,
            rerank_executed=False,
            swap_decision=swap_decision,
            global_direction=global_direction,
        )
        _MATCH_CACHE[cache_key] = None
        return None

    raw_tracks = search_track(
        access_token=access_token,
        title=search_title,
        artist=search_artist,
        market=market,
        limit=3,
    )
    query_for_log = query

    if not raw_tracks:
        fallback_query = f'{search_title} {search_artist}'.strip()
        raw_tracks = search_tracks_query(
            access_token=access_token,
            query=fallback_query,
            market=market,
            limit=3,
        )
        query_for_log = f'{query} -> {fallback_query}'

    scored_candidates: List[Dict[str, Any]] = []
    for track in raw_tracks:
        score, detail = compute_match_score(search_title, search_artist, track)
        scored_candidates.append(
            _candidate_to_result(
                track,
                score,
                detail,
                search_title=search_title,
                search_artist=search_artist,
            )
        )
    scored_candidates.sort(key=lambda item: item['score'], reverse=True)

    if not scored_candidates:
        _log_match(
            input_title=input_title,
            input_artist=input_artist,
            query=query_for_log,
            cache_status='miss',
            candidate_count=0,
            selected='none',
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
        query=query_for_log,
        cache_status='miss',
        candidate_count=len(scored_candidates),
        selected=selected,
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
