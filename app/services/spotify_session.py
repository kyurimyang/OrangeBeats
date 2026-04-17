import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.spotify_auth import refresh_access_token
from app.services.spotify_exceptions import SpotifyServiceError

_SESSION_FILE = Path(__file__).resolve().parents[2] / '.spotify_session.json'

spotify_auth_state_store: Dict[str, bool] = {}
spotify_token_store: Dict[str, Any] = {}


def _load_session() -> None:
    global spotify_token_store
    if not _SESSION_FILE.exists():
        spotify_token_store = {}
        return
    try:
        spotify_token_store = json.loads(_SESSION_FILE.read_text(encoding='utf-8'))
        if not isinstance(spotify_token_store, dict):
            spotify_token_store = {}
    except Exception:
        spotify_token_store = {}


def _save_session() -> None:
    try:
        _SESSION_FILE.write_text(
            json.dumps(spotify_token_store, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except Exception as e:
        print('spotify session save failed =', str(e))


def _now_ts() -> int:
    return int(time.time())


def save_token_data(token_data: Dict[str, Any]) -> None:
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token') or spotify_token_store.get('latest_refresh_token')
    expires_in = int(token_data.get('expires_in') or 3600)

    if access_token:
        spotify_token_store['latest_access_token'] = access_token
    if refresh_token:
        spotify_token_store['latest_refresh_token'] = refresh_token

    spotify_token_store['expires_at'] = _now_ts() + max(60, expires_in - 90)
    _save_session()


def clear_tokens() -> None:
    spotify_token_store.clear()
    _save_session()


def get_refresh_token() -> Optional[str]:
    return spotify_token_store.get('latest_refresh_token')


def get_access_token() -> Optional[str]:
    return spotify_token_store.get('latest_access_token')


def is_logged_in() -> bool:
    return bool(get_access_token() or get_refresh_token())


def ensure_valid_access_token() -> str:
    access_token = get_access_token()
    expires_at = int(spotify_token_store.get('expires_at') or 0)
    now = _now_ts()

    if access_token and expires_at and now < expires_at:
        return access_token

    refresh_token = get_refresh_token()
    if not refresh_token:
        raise SpotifyServiceError('Spotify 로그인이 만료되었습니다. 다시 로그인해주세요.')

    refreshed = refresh_access_token(refresh_token)
    if refresh_token and not refreshed.get('refresh_token'):
        refreshed['refresh_token'] = refresh_token
    save_token_data(refreshed)

    new_access_token = get_access_token()
    if not new_access_token:
        raise SpotifyServiceError('Spotify access token 갱신에 실패했습니다.')
    return new_access_token


_load_session()
