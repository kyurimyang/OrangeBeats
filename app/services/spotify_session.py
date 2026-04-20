import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.spotify_auth import refresh_access_token
from app.services.spotify_exceptions import SpotifyServiceError

_BASE_DIR = Path(__file__).resolve().parents[2]
_SESSION_FILE = _BASE_DIR / '.spotify_session.json'
_STATE_FILE = _BASE_DIR / '.spotify_auth_states.json'
_AUTH_STATE_TTL_SECONDS = 600

spotify_token_store: Dict[str, Any] = {}


def _now_ts() -> int:
    return int(time.time())


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _write_json_dict(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _refresh_token_store() -> Dict[str, Any]:
    global spotify_token_store
    spotify_token_store = _read_json_dict(_SESSION_FILE)
    return spotify_token_store


def _prune_auth_states(states: Dict[str, Any], now: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    current_ts = now or _now_ts()
    cleaned: Dict[str, Dict[str, Any]] = {}

    for state, raw_value in states.items():
        if not isinstance(raw_value, dict):
            continue

        created_at = int(raw_value.get('created_at') or 0)
        if created_at <= 0 or current_ts - created_at > _AUTH_STATE_TTL_SECONDS:
            continue

        frontend_origin = raw_value.get('frontend_origin')
        cleaned[state] = {
            'created_at': created_at,
            'frontend_origin': frontend_origin if isinstance(frontend_origin, str) else '',
        }

    return cleaned


def save_auth_state(state: str, frontend_origin: str) -> None:
    states = _prune_auth_states(_read_json_dict(_STATE_FILE))
    states[state] = {
        'created_at': _now_ts(),
        'frontend_origin': frontend_origin,
    }
    _write_json_dict(_STATE_FILE, states)


def pop_auth_state(state: str) -> Optional[Dict[str, Any]]:
    states = _prune_auth_states(_read_json_dict(_STATE_FILE))
    state_payload = states.pop(state, None)
    _write_json_dict(_STATE_FILE, states)
    return state_payload


def save_token_data(token_data: Dict[str, Any]) -> None:
    global spotify_token_store

    current_store = _refresh_token_store()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token') or current_store.get('latest_refresh_token')
    expires_in = int(token_data.get('expires_in') or 3600)

    updated_store = dict(current_store)
    if access_token:
        updated_store['latest_access_token'] = access_token
    if refresh_token:
        updated_store['latest_refresh_token'] = refresh_token

    updated_store['expires_at'] = _now_ts() + max(60, expires_in - 90)
    spotify_token_store = updated_store

    try:
        _write_json_dict(_SESSION_FILE, spotify_token_store)
    except Exception as e:
        print('spotify session save failed =', str(e))


def clear_tokens() -> None:
    global spotify_token_store

    spotify_token_store = {}
    try:
        _write_json_dict(_SESSION_FILE, spotify_token_store)
    except Exception as e:
        print('spotify session clear failed =', str(e))


def get_refresh_token() -> Optional[str]:
    return _refresh_token_store().get('latest_refresh_token')


def get_access_token() -> Optional[str]:
    return _refresh_token_store().get('latest_access_token')


def is_logged_in() -> bool:
    store = _refresh_token_store()
    return bool(store.get('latest_access_token') or store.get('latest_refresh_token'))


def ensure_valid_access_token() -> str:
    store = _refresh_token_store()
    access_token = store.get('latest_access_token')
    expires_at = int(store.get('expires_at') or 0)
    now = _now_ts()

    if access_token and expires_at and now < expires_at:
        return access_token

    refresh_token = store.get('latest_refresh_token')
    if not refresh_token:
        raise SpotifyServiceError('Spotify 로그인이 만료되었습니다. 다시 로그인해 주세요.')

    refreshed = refresh_access_token(refresh_token)
    if refresh_token and not refreshed.get('refresh_token'):
        refreshed['refresh_token'] = refresh_token
    save_token_data(refreshed)

    new_access_token = _refresh_token_store().get('latest_access_token')
    if not new_access_token:
        raise SpotifyServiceError('Spotify access token 갱신에 실패했습니다.')
    return new_access_token


_refresh_token_store()
