from typing import Any, Dict, List, Optional

from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_http import spotify_request

SPOTIFY_API_BASE = 'https://api.spotify.com/v1'


def _handle_response_error(resp, default_message: str) -> None:
    if resp is None:
        raise SpotifyServiceError(default_message)
    if resp.status_code == 429:
        retry_after = resp.headers.get('Retry-After', 'unknown')
        raise SpotifyServiceError(f'{default_message}: 429 / Too many requests (retry_after={retry_after})')
    raise SpotifyServiceError(f'{default_message}: {resp.status_code} / {resp.text}')


def get_current_user_profile(access_token: str) -> Dict[str, Any]:
    url = f'{SPOTIFY_API_BASE}/me'
    resp = spotify_request('GET', url, access_token=access_token)
    if resp.status_code != 200:
        _handle_response_error(resp, '사용자 정보 조회 실패')
    return resp.json()


def create_playlist(
    access_token: str,
    name: str,
    description: str = '',
    public: bool = True,
) -> Dict[str, Any]:
    url = f'{SPOTIFY_API_BASE}/me/playlists'
    payload = {'name': name[:100], 'description': description[:300], 'public': public}
    resp = spotify_request('POST', url, access_token=access_token, json=payload)
    if resp.status_code not in (200, 201):
        _handle_response_error(resp, '플레이리스트 생성 실패')
    return resp.json()


def search_tracks_query(
    access_token: str,
    query: str,
    market: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    query = (query or '').strip()
    if not query:
        return []

    limit = max(1, min(int(limit), 5))
    params = {'q': query, 'type': 'track', 'market': market or 'KR', 'limit': limit}

    url = f'{SPOTIFY_API_BASE}/search'
    resp = spotify_request('GET', url, access_token=access_token, params=params)
    if resp.status_code != 200:
        _handle_response_error(resp, '곡 검색 실패')

    data = resp.json()
    return data.get('tracks', {}).get('items', [])


def search_track(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 5))
    query_parts = []
    if title:
        query_parts.append(f'track:"{title}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    query = ' '.join(query_parts).strip()
    return search_tracks_query(access_token=access_token, query=query, market=market, limit=limit)


def add_tracks_to_playlist(
    access_token: str,
    playlist_id: str,
    track_uris: List[str],
) -> Dict[str, Any]:
    url = f'{SPOTIFY_API_BASE}/playlists/{playlist_id}/items'
    snapshot_result: Dict[str, Any] = {}

    for i in range(0, len(track_uris), 100):
        chunk = track_uris[i:i + 100]
        payload = {'uris': chunk}
        resp = spotify_request('POST', url, access_token=access_token, json=payload)
        if resp.status_code not in (200, 201):
            _handle_response_error(resp, '곡 추가 실패')
        snapshot_result = resp.json()

    return snapshot_result
