import re
from typing import Any, Dict, List, Optional, Tuple

from app.constants.pipeline_params import SPOTIFY_HIGH_CONF, SPOTIFY_MID_CONF
from app.services.spotify_api import search_track, search_tracks_query
from app.services.spotify_common import (
    _artist_variants,
    _clean_track_title_for_search,
    _is_short_or_generic_title,
    _title_variants,
    compute_match_score,
)

_MATCH_CACHE: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
_SEARCH_CACHE: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}

EARLY_STOP_SCORE = 0.78
SWAPPED_MIN_SCORE = 0.72
MAX_CACHE_SIZE = 300


def _candidate_to_result(
    track: Dict[str, Any],
    score: float,
    detail: Dict[str, float],
    *,
    search_title: str,
    search_artist: Optional[str],
    orientation: str,
) -> Dict[str, Any]:
    return {
        'id': track.get('id'),
        'uri': track.get('uri'),
        'name': track.get('name', ''),
        'artists': [a.get('name', '') for a in track.get('artists', [])],
        'album': (track.get('album') or {}).get('name', ''),
        'score': score,
        'score_detail': detail,
        'orientation': orientation,
        'llm_reranked': False,
        'llm_confidence': '',
        'llm_reason': '',
        'search_title': search_title,
        'search_artist': search_artist or '',
    }


def _merge_best_candidates(existing: List[Dict[str, Any]], new_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_uri = {item['uri']: item for item in existing if item.get('uri')}
    for item in new_candidates:
        uri = item.get('uri')
        if not uri:
            continue
        prev = by_uri.get(uri)
        if prev is None or item['score'] > prev['score']:
            by_uri[uri] = item
    return sorted(by_uri.values(), key=lambda x: x['score'], reverse=True)


def _search_and_score(
    access_token: str,
    *,
    input_title: str,
    input_artist: Optional[str],
    search_title: str,
    search_artist: Optional[str],
    market: Optional[str],
    orientation: str,
) -> List[Dict[str, Any]]:
    cache_key = (
        (search_title or '').strip().lower(),
        (search_artist or '').strip().lower(),
        (market or '').strip().upper(),
    )
    raw_tracks = _SEARCH_CACHE.get(cache_key)
    if raw_tracks is None:
        if search_artist:
            raw_tracks = search_track(
                access_token=access_token,
                title=search_title,
                artist=search_artist,
                market=market,
                limit=3,
            )
        else:
            raw_tracks = search_tracks_query(
                access_token=access_token,
                query=search_title,
                market=market,
                limit=3,
            )
        if len(_SEARCH_CACHE) >= MAX_CACHE_SIZE:
            _SEARCH_CACHE.clear()
        _SEARCH_CACHE[cache_key] = raw_tracks

    scored = []
    for track in raw_tracks:
        score, detail = compute_match_score(input_title, input_artist or '', track)
        scored.append(
            _candidate_to_result(
                track,
                score,
                detail,
                search_title=search_title,
                search_artist=search_artist,
                orientation=orientation,
            )
        )
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored


def _best_score(candidates: List[Dict[str, Any]]) -> float:
    if not candidates:
        return 0.0
    return candidates[0]['score']


def _is_artist_like_text(value: str) -> bool:
    normalized = (value or '').lower()
    if re.search(r'(?:,|&| x | feat\.?|ft\.?)', normalized):
        return True
    return len(_artist_variants(value)) > 1


def _should_try_swapped(
    input_title: str,
    input_artist: str,
    best_candidates: List[Dict[str, Any]],
) -> bool:
    if not input_artist:
        return False
    if _best_score(best_candidates) >= EARLY_STOP_SCORE:
        return False

    best = best_candidates[0] if best_candidates else None
    weak_artist_alignment = best is None or best.get('score_detail', {}).get('artist_score', 0.0) < 0.25
    artist_like_title = _is_artist_like_text(input_title)
    title_like_artist = _clean_track_title_for_search(input_artist) != input_artist

    return weak_artist_alignment and (artist_like_title or title_like_artist)


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    cache_key = ((title or '').strip().lower(), (artist or '').strip().lower())
    if cache_key in _MATCH_CACHE:
        return _MATCH_CACHE[cache_key]

    input_title = (title or '').strip()
    input_artist = (artist or '').strip()
    title_variants = _title_variants(_clean_track_title_for_search(input_title))
    artist_variants = _artist_variants(input_artist) if input_artist else [None]

    best_candidates: List[Dict[str, Any]] = []

    # pass 1: title + artist exact-ish
    first_title = title_variants[0] if title_variants else input_title
    first_artist = artist_variants[0] if artist_variants else None
    best_candidates = _merge_best_candidates(
        best_candidates,
        _search_and_score(
            access_token,
            input_title=input_title,
            input_artist=input_artist,
            search_title=first_title,
            search_artist=first_artist,
            market=market,
            orientation='title_artist',
        ),
    )

    if best_candidates and best_candidates[0]['score'] >= SPOTIFY_HIGH_CONF:
        best = dict(best_candidates[0])
        best['top_candidates'] = best_candidates[:3]
        _MATCH_CACHE[cache_key] = best
        return best

    if best_candidates and best_candidates[0]['score'] >= EARLY_STOP_SCORE:
        best = dict(best_candidates[0])
        best['top_candidates'] = best_candidates[:3]
        _MATCH_CACHE[cache_key] = best
        return best

    # pass 2: only one controlled fallback
    use_artist_first = bool(input_artist) and _is_short_or_generic_title(input_title)
    if use_artist_first:
        for artist_variant in artist_variants[:2]:
            if not artist_variant:
                continue
            query = f'artist:"{artist_variant}" {first_title}'
            candidates = _search_and_score(
                access_token,
                input_title=input_title,
                input_artist=input_artist,
                search_title=query,
                search_artist=None,
                market=market,
                orientation='artist_first',
            )
            best_candidates = _merge_best_candidates(best_candidates, candidates)
            if best_candidates and best_candidates[0]['score'] >= SPOTIFY_HIGH_CONF:
                break
    elif _best_score(best_candidates) < EARLY_STOP_SCORE:
        for title_variant in title_variants[1:2]:
            candidates = _search_and_score(
                access_token,
                input_title=input_title,
                input_artist=input_artist,
                search_title=title_variant,
                search_artist=first_artist,
                market=market,
                orientation='title_fallback',
            )
            best_candidates = _merge_best_candidates(best_candidates, candidates)
            if best_candidates and best_candidates[0]['score'] >= SPOTIFY_HIGH_CONF:
                break

    if _should_try_swapped(input_title, input_artist, best_candidates):
        swapped_title = _clean_track_title_for_search(input_artist) or input_artist
        swapped_artist_variants = _artist_variants(input_title)
        swapped_artist = swapped_artist_variants[0] if swapped_artist_variants else input_title
        swapped_candidates = _search_and_score(
            access_token,
            input_title=input_artist,
            input_artist=input_title,
            search_title=swapped_title,
            search_artist=swapped_artist,
            market=market,
            orientation='swapped',
        )
        best_candidates = _merge_best_candidates(best_candidates, swapped_candidates)

    if not best_candidates:
        _MATCH_CACHE[cache_key] = None
        return None

    best = dict(best_candidates[0])
    best['top_candidates'] = best_candidates[:3]
    min_score = SPOTIFY_MID_CONF
    if best.get('orientation') == 'swapped':
        min_score = max(min_score, SWAPPED_MIN_SCORE)

    if best['score'] < min_score:
        _MATCH_CACHE[cache_key] = None
        return None

    if len(_MATCH_CACHE) >= MAX_CACHE_SIZE:
        _MATCH_CACHE.clear()
    _MATCH_CACHE[cache_key] = best
    return best
