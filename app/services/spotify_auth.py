import base64
from typing import Any, Dict
from urllib.parse import urlencode

import requests

from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from app.services.spotify_exceptions import SpotifyServiceError

SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"


def _basic_auth_header() -> str:
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


def get_spotify_login_url(state: str) -> str:
    scope = "playlist-modify-public playlist-modify-private ugc-image-upload"
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