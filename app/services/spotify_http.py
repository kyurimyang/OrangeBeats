import json
from pathlib import Path
from typing import Dict, Optional

import requests

from app.services.spotify_exceptions import SpotifyServiceError

DEFAULT_TIMEOUT = 20
_RATE_LIMIT_FILE = Path(__file__).resolve().parents[2] / ".spotify_rate_limit.json"
_rate_limited_until = 0.0
_rate_limit_message: Optional[str] = None


def _load_rate_limit_state() -> None:
    global _rate_limited_until
    global _rate_limit_message

    if not _RATE_LIMIT_FILE.exists():
        _rate_limited_until = 0.0
        _rate_limit_message = None
        return

    try:
        data = json.loads(_RATE_LIMIT_FILE.read_text(encoding="utf-8"))
        _rate_limited_until = float(data.get("rate_limited_until") or 0.0)
        message = (data.get("message") or "").strip()
        _rate_limit_message = message or None
    except Exception:
        _rate_limited_until = 0.0
        _rate_limit_message = None


def _auth_headers(access_token: str, content_type: str = "application/json") -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def spotify_request(
    method: str,
    url: str,
    *,
    access_token: Optional[str] = None,
    params: Optional[Dict] = None,
    json: Optional[Dict] = None,
    data=None,
    content_type: str = "application/json",
    timeout: int = DEFAULT_TIMEOUT,
):
    if not access_token:
        raise SpotifyServiceError("Spotify access token이 없습니다.")

    headers = _auth_headers(access_token, content_type=content_type)
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise SpotifyServiceError(f"Spotify 요청 실패: {str(exc)}") from exc

    if response.status_code == 429:
        retry_after_header = response.headers.get("Retry-After")
        try:
            retry_after = max(1, int(retry_after_header or "60"))
        except ValueError:
            retry_after = 60
        raise SpotifyServiceError(
            f"Spotify API rate limit active: 429 / Too many requests (retry_after={retry_after})"
        )

    return response


_load_rate_limit_state()
