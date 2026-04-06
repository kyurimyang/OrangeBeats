import base64
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyServiceError(Exception):
    pass


def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


def get_spotify_login_url(state: str) -> str:
    scope = "user-read-private playlist-modify-public playlist-modify-private"
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": scope,
        "state": state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_ACCOUNTS_BASE}/authorize?{urlencode(params)}"


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


def _normalize_text(value: str) -> str:
    value = (value or "").lower().strip()
    value = value.replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)
    value = re.sub(r"[^\w가-힣\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _clean_track_title_for_search(title: str) -> str:
    value = (title or "").strip()

    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)

    remove_patterns = [
        r"\bfeat\.?.*$",
        r"\bft\.?.*$",
        r"\bwith\b.*$",
        r"\bprod\.?.*$",
        r"\bremaster(ed)?\b.*$",
        r"\blive\b.*$",
        r"\bost\b.*$",
        r"\bver\.?\b.*$",
        r"\bversion\b.*$",
        r"\bsped up\b.*$",
        r"\bslowed\b.*$",
    ]
    for pattern in remove_patterns:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)

    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _artist_variants(artist: Optional[str]) -> List[Optional[str]]:
    if not artist:
        return [None]

    cleaned = artist.strip()
    variants: List[Optional[str]] = [cleaned]

    split_parts = re.split(r"\s*(?:,|&| x | feat\.?|ft\.?)\s*", cleaned, flags=re.IGNORECASE)
    for part in split_parts:
        part = part.strip()
        if part and part not in variants:
            variants.append(part)

    return variants


def get_current_user_profile(access_token: str) -> Dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}/me"
    resp = requests.get(url, headers=_auth_headers(access_token), timeout=20)
    if resp.status_code != 200:
        raise SpotifyServiceError(f"사용자 정보 조회 실패: {resp.status_code} / {resp.text}")
    return resp.json()


def create_playlist(access_token: str, name: str, description: str = "", public: bool = True) -> Dict[str, Any]:
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


def _candidate_score(candidate: Dict[str, Any], title: str, artist: Optional[str]) -> float:
    target_title = _normalize_text(title)
    target_title_clean = _normalize_text(_clean_track_title_for_search(title))
    target_artist = _normalize_text(artist or "")

    cand_title_raw = candidate.get("name", "")
    cand_title = _normalize_text(cand_title_raw)
    cand_title_clean = _normalize_text(_clean_track_title_for_search(cand_title_raw))

    cand_artists = " ".join(a.get("name", "") for a in candidate.get("artists", []))
    cand_artist_norm = _normalize_text(cand_artists)

    title_score_raw = SequenceMatcher(None, target_title, cand_title).ratio() if target_title and cand_title else 0.0
    title_score_clean = SequenceMatcher(None, target_title_clean, cand_title_clean).ratio() if target_title_clean and cand_title_clean else 0.0
    title_score = max(title_score_raw, title_score_clean)

    artist_score = 0.0
    if target_artist and cand_artist_norm:
        artist_score = SequenceMatcher(None, target_artist, cand_artist_norm).ratio()

    score = title_score * 0.8 + artist_score * 0.2

    if target_title_clean and target_title_clean == cand_title_clean:
        score += 0.12

    if target_artist and target_artist in cand_artist_norm:
        score += 0.08

    bad_tokens = ["instrumental", "remix", "live", "sped up", "slowed"]
    if any(token in cand_title for token in bad_tokens):
        score -= 0.06

    return round(score, 4)


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    seen_ids = set()
    ranked: List[Dict[str, Any]] = []

    raw_title = (title or "").strip()
    clean_title = _clean_track_title_for_search(raw_title)

    title_variants = []
    for t in [raw_title, clean_title]:
        if t and t not in title_variants:
            title_variants.append(t)

    artist_variants = _artist_variants(artist)
    search_cases = []

    # 1) title + artist
    for t in title_variants:
        for a in artist_variants:
            if t and a:
                search_cases.append((t, a))

    # 2) title only
    for t in title_variants:
        if t:
            search_cases.append((t, None))

    dedup_cases = []
    seen_cases = set()
    for case in search_cases:
        if case not in seen_cases:
            seen_cases.add(case)
            dedup_cases.append(case)

    for search_title, search_artist in dedup_cases:
        candidates = search_track(
            access_token=access_token,
            title=search_title,
            artist=search_artist,
            market=market,
            limit=10,
        )

        for candidate in candidates:
            candidate_id = candidate.get("id")
            if not candidate_id or candidate_id in seen_ids:
                continue

            seen_ids.add(candidate_id)
            ranked.append({
                "uri": candidate["uri"],
                "name": candidate.get("name", ""),
                "artists": [a.get("name", "") for a in candidate.get("artists", [])],
                "score": _candidate_score(candidate, title=raw_title, artist=artist),
                "search_title": search_title,
                "search_artist": search_artist or "",
            })

    if not ranked:
        return None

    ranked.sort(key=lambda x: x["score"], reverse=True)
    best = ranked[0]

    if best["score"] < 0.66:
        return None

    return best


def add_tracks_to_playlist(access_token: str, playlist_id: str, track_uris: List[str]) -> Dict[str, Any]:
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


def _is_suspicious_song(song: Dict[str, Any]) -> bool:
    title = (song.get("title") or "").strip()
    artist = (song.get("artist") or "").strip()

    if not title:
        return True

    if artist and _normalize_text(title) == _normalize_text(artist):
        return True

    return False


def create_playlist_from_songs(
    access_token: str,
    playlist_name: str,
    songs: List[Dict[str, str]],
    playlist_description: str = "",
    public: bool = True,
) -> Dict[str, Any]:
    if not songs:
        raise SpotifyServiceError("생성할 곡 목록이 없습니다.")

    playlist = create_playlist(
        access_token=access_token,
        name=playlist_name,
        description=playlist_description,
        public=public,
    )

    matched_uris: List[str] = []
    matched_debug: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_uris = set()

    for song in songs:
        title = (song.get("title") or "").strip()
        artist = (song.get("artist") or "").strip() or None

        if not title:
            unmatched.append({"song": song, "reason": "title 없음"})
            continue

        if _is_suspicious_song(song):
            unmatched.append({"song": song, "reason": "artist/title 동일 또는 정보 부족"})
            continue

        match = pick_best_track_match(
            access_token=access_token,
            title=title,
            artist=artist,
            market=None,
        )

        if match:
            if match["uri"] not in seen_uris:
                seen_uris.add(match["uri"])
                matched_uris.append(match["uri"])

            matched_debug.append({
                "input": {"artist": artist or "", "title": title},
                "matched_name": match["name"],
                "matched_artists": match["artists"],
                "score": match["score"],
                "search_title": match.get("search_title", ""),
                "search_artist": match.get("search_artist", ""),
            })
        else:
            unmatched.append({"song": song, "reason": "spotify 검색 실패 또는 저신뢰 매칭"})

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
        "matched": matched_debug,
        "unmatched": unmatched,
    }