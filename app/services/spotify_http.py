import time
import json
from pathlib import Path
from typing import Dict, Optional

import requests

from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_session import ensure_valid_access_token, save_token_data, get_refresh_token
from app.services.spotify_auth import refresh_access_token


DEFAULT_TIMEOUT = 20
_rate_limited_until = 0.0
_rate_limit_message: Optional[str] = None
_RATE_LIMIT_FILE = Path(__file__).resolve().parents[2] / '.spotify_rate_limit.json'


def _load_rate_limit_state() -> None:
    global _rate_limited_until
    global _rate_limit_message

    if not _RATE_LIMIT_FILE.exists():
        _rate_limited_until = 0.0
        _rate_limit_message = None
        return

    try:
        data = json.loads(_RATE_LIMIT_FILE.read_text(encoding='utf-8'))
        _rate_limited_until = float(data.get('rate_limited_until') or 0.0)
        message = (data.get('message') or '').strip()
        _rate_limit_message = message or None
    except Exception:
        _rate_limited_until = 0.0
        _rate_limit_message = None


def _save_rate_limit_state() -> None:
    if _rate_limited_until <= 0:
        try:
            if _RATE_LIMIT_FILE.exists():
                _RATE_LIMIT_FILE.unlink()
        except Exception:
            pass
        return

    payload = {
        'rate_limited_until': _rate_limited_until,
        'message': _rate_limit_message or '',
    }
    try:
        _RATE_LIMIT_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except Exception:
        pass


def _clear_rate_limit_state() -> None:
    global _rate_limited_until
    global _rate_limit_message

    _rate_limited_until = 0.0
    _rate_limit_message = None
    _save_rate_limit_state()


def _auth_headers(access_token: str, content_type: str = 'application/json') -> Dict[str, str]:
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    if content_type:
        headers['Content-Type'] = content_type
    return headers


def spotify_request(
    method: str,
    url: str,
    *,
    access_token: Optional[str] = None,
    params: Optional[Dict] = None,
    json: Optional[Dict] = None,
    data=None,
    content_type: str = 'application/json',
    timeout: int = DEFAULT_TIMEOUT,
):
    global _rate_limited_until
    global _rate_limit_message

    token = access_token or ensure_valid_access_token()
    last_response = None

    for attempt in range(2):
        headers = _auth_headers(token, content_type=content_type)
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
        except requests.RequestException as e:
            raise SpotifyServiceError(f'Spotify 요청 실패: {str(e)}') from e

        last_response = response

        if response.status_code == 429:
            retry_after_header = response.headers.get('Retry-After')
            try:
                retry_after = max(1, int(retry_after_header or '60'))
            except ValueError:
                retry_after = 60
            raise SpotifyServiceError(
                f'Spotify API rate limit active: 429 / Too many requests (retry_after={retry_after})'
            )

        if response.status_code != 401:
            return response

        refresh_token = get_refresh_token()
        if not refresh_token or attempt == 1:
            break

        refreshed = refresh_access_token(refresh_token)
        if refresh_token and not refreshed.get('refresh_token'):
            refreshed['refresh_token'] = refresh_token
        save_token_data(refreshed)
        token = refreshed.get('access_token') or token

    return last_response


_load_rate_limit_state()
