from typing import Any, Dict, List

from app.services.spotify_api import add_tracks_to_playlist, create_playlist
from app.services.spotify_common import _is_suspicious_song, build_match_cache_key
from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_matching import get_match_debug, pick_best_track_match

LOW_CONF_MIN_SCORE = 0.15
ALLOWED_LOW_CONF_REASONS = {
    "artist_alias_candidate",
    "title_matched_artist_alias_candidate",
    "artist_matched_title_mismatch",
    "top_candidate_artist_romanization_title_mismatch",
    "title_alias_candidate",
}


def _low_confidence_allowed_reason(match: Dict[str, Any]) -> str:
    for key in ("reason", "match_status", "low_confidence_reason"):
        value = str(match.get(key) or "").strip()
        if value in ALLOWED_LOW_CONF_REASONS:
            return value
    return ""


def _low_confidence_skip_reason(match: Dict[str, Any]) -> str:
    if not match.get("uri"):
        return "missing_uri"
    if float(match.get("score") or 0.0) < LOW_CONF_MIN_SCORE:
        return "score_too_low"
    if not _low_confidence_allowed_reason(match):
        return "reason_not_allowed"
    return ""


def create_playlist_from_songs(
    access_token: str,
    playlist_name: str,
    songs: List[Dict[str, str]],
    playlist_description: str = '',
    public: bool = True,
) -> Dict[str, Any]:
    if not songs:
        raise SpotifyServiceError('생성할 곡 목록이 없습니다.')

    playlist = create_playlist(
        access_token=access_token,
        name=playlist_name,
        description=playlist_description,
        public=public,
    )

    matched_uris: List[str] = []
    playlist_uris: List[str] = []
    matched_debug: List[Dict[str, Any]] = []
    low_confidence: List[Dict[str, Any]] = []
    added_low_confidence: List[Dict[str, Any]] = []
    skipped_low_confidence: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_uris = set()
    request_match_cache: Dict[tuple[str, str], Any] = {}

    for song in songs:
        title = (song.get('title') or '').strip()
        artist = (song.get('artist') or '').strip() or None
        song_meta = {
            'raw': song.get('raw', ''),
            'left': song.get('left', ''),
            'right': song.get('right', ''),
            'swap_applied': song.get('swap_applied', False),
            'global_direction': song.get('global_direction', 'per_line'),
            'chosen_case': song.get('chosen_case', 'original'),
            'score': song.get('score', 0.0),
            'reason': song.get('reason', ''),
            'swap_guard_applied': song.get('swap_guard_applied', False),
            'swap_guard_reason': song.get('swap_guard_reason', ''),
        }

        if not title:
            unmatched.append({'song': song, 'reason': 'title 없음'})
            continue

        if _is_suspicious_song(song):
            unmatched.append({'song': song, 'reason': 'artist/title 동일 또는 정보 부족'})
            continue

        cache_key = build_match_cache_key(title, artist or '')
        if cache_key in request_match_cache:
            match = request_match_cache[cache_key]
        else:
            match = pick_best_track_match(
                access_token=access_token,
                title=title,
                artist=artist,
                market='KR',
                song_meta=song_meta,
            )
            request_match_cache[cache_key] = match

        if not match:
            debug = get_match_debug(title, artist or '')
            unmatched.append({
                'song': song,
                'reason': debug.get('unmatched_reason') or 'spotify 검색 실패 또는 저신뢰 매칭',
                'search_title': debug.get('search_title', title),
                'search_artist': debug.get('search_artist', artist or ''),
                'chosen_case': debug.get('selected_case', song_meta['chosen_case']),
                'top_candidates': debug.get('top_candidates', []),
                'case_results': debug.get('case_results', []),
            })
            continue

        match_status = match.get('match_status', 'matched')
        if match_status != 'matched':
            low_conf_reason = match.get('low_confidence_reason', '') or match.get('reason', '')
            low_confidence_item = {
                'input': {
                    'artist': artist or '',
                    'title': title,
                },
                'matched_name': match.get('name', ''),
                'matched_artists': match.get('artists', []),
                'score': match.get('score', 0.0),
                'match_status': match_status,
                'reason': low_conf_reason,
                'search_title': match.get('search_title', ''),
                'search_artist': match.get('search_artist', ''),
                'chosen_case': match.get('chosen_case', song_meta['chosen_case']),
                'swap_applied': song_meta['swap_applied'],
                'global_direction': song_meta['global_direction'],
                'parse_reason': song_meta['reason'],
                'parse_score': song_meta['score'],
                'top_candidates': [
                    {
                        'name': candidate['name'],
                        'artists': candidate['artists'],
                        'score': candidate['score'],
                        'popularity': candidate.get('popularity', 0),
                        'orientation': candidate['orientation'],
                        'chosen_case': candidate.get('chosen_case', match.get('chosen_case', song_meta['chosen_case'])),
                        'match_status': candidate.get('match_status', ''),
                        'low_confidence_reason': candidate.get('low_confidence_reason', ''),
                    }
                    for candidate in match.get('top_candidates', [])
                ],
            }
            low_confidence.append({
                **low_confidence_item,
            })
            skip_reason = _low_confidence_skip_reason(match)
            if skip_reason:
                skipped_low_confidence.append({
                    'input': {
                        'artist': artist or '',
                        'title': title,
                    },
                    'matched_name': match.get('name', ''),
                    'score': match.get('score', 0.0),
                    'skip_reason': skip_reason,
                })
            else:
                uri = match.get('uri')
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    playlist_uris.append(uri)
                added_low_confidence.append({
                    'input': {
                        'artist': artist or '',
                        'title': title,
                    },
                    'matched_name': match.get('name', ''),
                    'matched_artists': match.get('artists', []),
                    'score': match.get('score', 0.0),
                    'reason': _low_confidence_allowed_reason(match) or low_conf_reason,
                    'match_status': match_status,
                    'uri': uri,
                })
            continue

        uri = match.get('uri')
        if uri and uri not in seen_uris:
            seen_uris.add(uri)
            matched_uris.append(uri)
            playlist_uris.append(uri)

        matched_debug.append({
            'input': {
                'artist': artist or '',
                'title': title,
            },
            'matched_name': match.get('name', ''),
            'matched_artists': match.get('artists', []),
            'score': match.get('score', 0.0),
            'chosen_case': match.get('chosen_case', song_meta['chosen_case']),
            'reason': match.get('reason', ''),
            'orientation': match.get('orientation', 'title_artist'),
            'llm_reranked': False,
            'llm_confidence': '',
            'llm_reason': '',
            'search_title': match.get('search_title', ''),
            'search_artist': match.get('search_artist', ''),
            'swap_applied': song_meta['swap_applied'],
            'global_direction': song_meta['global_direction'],
            'parse_reason': song_meta['reason'],
            'parse_score': song_meta['score'],
            'swap_guard_applied': song_meta['swap_guard_applied'],
            'swap_guard_reason': song_meta['swap_guard_reason'],
            'top_candidates': [
                {
                    'name': candidate['name'],
                    'artists': candidate['artists'],
                    'score': candidate['score'],
                    'popularity': candidate.get('popularity', 0),
                    'orientation': candidate['orientation'],
                    'chosen_case': candidate.get('chosen_case', match.get('chosen_case', song_meta['chosen_case'])),
                    'match_status': candidate.get('match_status', ''),
                    'low_confidence_reason': candidate.get('low_confidence_reason', ''),
                }
                for candidate in match.get('top_candidates', [])
            ],
        })

    if playlist_uris:
        add_tracks_to_playlist(
            access_token=access_token,
            playlist_id=playlist['id'],
            track_uris=playlist_uris,
        )

    return {
        'playlist_id': playlist['id'],
        'playlist_url': playlist['external_urls']['spotify'],
        'matched_count': len(matched_uris),
        'unmatched_count': len(unmatched),
        'low_confidence_count': len(low_confidence),
        'added_low_confidence_count': len(added_low_confidence),
        'added_low_confidence': added_low_confidence,
        'skipped_low_confidence_count': len(skipped_low_confidence),
        'skipped_low_confidence': skipped_low_confidence,
        'matched': matched_debug,
        'low_confidence': low_confidence,
        'unmatched': unmatched,
    }
