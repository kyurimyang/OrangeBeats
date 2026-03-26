import base64
from typing import Any, Dict,List,Optional
from urllib.parse import urlencode

import requests

from app.config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)

SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

class SpotifyServiceError(Exception):
    pass

def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic{encoded}"

# 사용자 Spotify 로그인/권한 동의 페이지 URL 생성
def get_spotify_login_url() -> str:
    scope = "playlist-modify-public playlist-modify-private"
    params = {
        "client_id" : SPOTIFY_CLIENT_ID,
        "response_type" : "code",
        "redirect_url" : SPOTIFY_REDIRECT_URI,
        "scope" : scope,
        "state" : state,
        "show_dialog" : "true", 
    }
    return f"{SPOTIFY_ACCOUNTS_BASE}/authorize?{urlencode(params)}"

# authorization code -> access token 교환
def exchange_code_for_token(code: str) -> Dict[str, Any]:
    url = f"{SPOTIFY_ACCOUNTS_BASE}/api/token"
    headers = {
        "Authorization": _basic_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    }

    resp = requests.post(url, headers=headers, data=data, timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"토큰 발급 실패: {resp.status_code} / {resp.text}")
    return resp.json()
    
 # refresh token으로 access token 재발급
def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    url = f"{SPOTIFY_ACCOUNTS_BASE}/api/token"
    headers = {
        "Authorization": _basic_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    resp = requests.post(url, headers=headers, data=data, timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"토큰 갱신 실패: {resp.status_code} / {resp.text}")
    return resp.json()

def _auth_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
def get_current_user_profile(access_token: str) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/me"
    resp = requests.get(url, headers=_auth_headers(access_token), timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"사용자 정보 조회 실패: {resp.status_code} / {resp.text}")
    return resp.json()

def create_playlist(
    access_token: str,
    user_id: str,
    name: str,
    description: str = "",
    public: bool = False,
) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"
    payload = {
        "name": name,
        "description": description,
        "public": public,
    }
    resp = requests.post(url, headers=_auth_headers(access_token), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise SpotifyServiceError(f"플레이리스트 생성 실패: {resp.status_code} / {resp.text}")
    return resp.json()

def search_track(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: str = "KR",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    #title + artist 기반 검색
    query = f'track:"{title}"'
    if artist:
        query += f' artist:"{artist}"'

    url = f"{SPOTIFY_API_BASE}/search"
    params = {
        "q": query,
        "type": "track",
        "market": market,
        "limit": limit,
    }

    resp = requests.get(url, headers=_auth_headers(access_token), params=params, timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"곡 검색 실패: {resp.status_code} / {resp.text}")

    data = resp.json()
    return data.get("tracks", {}).get("items", [])

#  1차: track+artist 정확 검색
#  2차: title만 검색
def pick_best_track_uri(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: str = "KR",
) -> Optional[str]:
    
    candidates = search_track(access_token, title=title, artist=artist, market=market, limit=5)
    if candidates:
        return candidates[0]["uri"]

    if artist:
        fallback_candidates = search_track(access_token, title=title, artist=None, market=market, limit=5)
        if fallback_candidates:
            return fallback_candidates[0]["uri"]

    return None

 
# Spotify playlist에 곡 추가(한 번에 최대 100개)
    
def add_tracks_to_playlist(
    access_token: str,
    playlist_id: str,
    track_uris: List[str],
) -> Dict[str, Any]:
   
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/items"

    snapshot_result = {}
    for i in range(0, len(track_uris), 100):
        chunk = track_uris[i:i + 100]
        payload = {"uris": chunk}
        resp = requests.post(url, headers=_auth_headers(access_token), json=payload, timeout=20)
        if resp.status_code not in (200, 201):
            raise SpotifyServiceError(f"곡 추가 실패: {resp.status_code} / {resp.text}")
        snapshot_result = resp.json()

    return snapshot_result

def create_playlist_from_songs(
    access_token: str,
    playlist_name: str,
    songs: List[Dict[str, str]],
    playlist_description: str = "Created by Paran Playlist AI",
    public: bool = False,
) -> Dict[str, Any]:
  
    user = get_current_user_profile(access_token)
    user_id = user["id"]

    playlist = create_playlist(
        access_token=access_token,
        user_id=user_id,
        name=playlist_name,
        description=playlist_description,
        public=public,
    )

    matched_uris = []
    unmatched = []

    for song in songs:
        title = (song.get("title") or "").strip()
        artist = (song.get("artist") or "").strip() or None

        if not title:
            unmatched.append({"song": song, "reason": "title 없음"})
            continue

        uri = pick_best_track_uri(
            access_token=access_token,
            title=title,
            artist=artist,
            market="KR",
        )

        if uri:
            matched_uris.append(uri)
        else:
            unmatched.append({"song": song, "reason": "spotify 검색 실패"})

    if matched_uris:
        add_tracks_to_playlist(
            access_token=access_token,
            playlist_id=playlist["id"],
            track_uris=matched_uris,
        )

    return {
        "playlist_id": playlist["id"],
        "playlist_url": playlist["external_urls"]["spotify"],
        "matched_count": len(matched_uris),
        "unmatched_count": len(unmatched),
        "unmatched": unmatched,
    }

