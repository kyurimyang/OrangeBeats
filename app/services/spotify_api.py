from typing import Any, Dict, List, Optional

import requests

from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_http import _auth_headers

SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def get_current_user_profile(access_token: str) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/me"
    resp = requests.get(url, headers=_auth_headers(access_token), timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"사용자 정보 조회 실패: {resp.status_code} / {resp.text}")
    return resp.json()


def create_playlist(
    access_token: str,
    name: str,
    description: str = "",
    public: bool = True,
) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    payload = {"name": name, "description": description, "public": public}
    resp = requests.post(url, headers=_auth_headers(access_token), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise SpotifyServiceError(f"플레이리스트 생성 실패: {resp.status_code} / {resp.text}")
    return resp.json()


def search_track(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    query_parts = []

    if title:
        query_parts.append(f'track:"{title}"')

    if artist:
        query_parts.append(f'artist:"{artist}"')

    query = " ".join(query_parts).strip()
    if not query:
        return []

    url = f"{SPOTIFY_API_BASE}/search"
    params = {"q": query, "type": "track", "limit": limit}
    if market:
        params["market"] = market

    resp = requests.get(url, headers=_auth_headers(access_token), params=params, timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"곡 검색 실패: {resp.status_code} / {resp.text}")

    data = resp.json()
    return data.get("tracks", {}).get("items", [])


def add_tracks_to_playlist(
    access_token: str,
    playlist_id: str,
    track_uris: List[str],
) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/items"
    snapshot_result: Dict[str, Any] = {}

    for i in range(0, len(track_uris), 100):
        chunk = track_uris[i:i + 100]
        payload = {"uris": chunk}
        resp = requests.post(url, headers=_auth_headers(access_token), json=payload, timeout=20)
        if resp.status_code not in (200, 201):
            raise SpotifyServiceError(f"곡 추가 실패: {resp.status_code} / {resp.text}")
        snapshot_result = resp.json()

    return snapshot_result