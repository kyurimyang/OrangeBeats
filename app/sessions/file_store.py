import json
import threading
import time
from pathlib import Path
from typing import Optional

from app.sessions.models import OAuthStateRecord, SpotifyTokenRecord

SESSION_FILE = Path("data/sessions.json")


def _empty_store() -> dict:
    return {"tokens": {}, "states": {}}


def _load() -> dict:
    if not SESSION_FILE.exists():
        return _empty_store()

    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _empty_store()

    if not isinstance(data, dict):
        return _empty_store()
    data.setdefault("tokens", {})
    data.setdefault("states", {})
    if not isinstance(data["tokens"], dict):
        data["tokens"] = {}
    if not isinstance(data["states"], dict):
        data["states"] = {}
    return data


def _save(data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class FileSpotifyTokenStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def get(self, session_id: str) -> Optional[SpotifyTokenRecord]:
        with self._lock:
            record = _load()["tokens"].get(session_id)
            if not record:
                return None
            return SpotifyTokenRecord(**record)

    def set(self, record: SpotifyTokenRecord) -> None:
        with self._lock:
            data = _load()
            data["tokens"][record.session_id] = {
                "session_id": record.session_id,
                "access_token": record.access_token,
                "refresh_token": record.refresh_token,
                "expires_at": record.expires_at,
                "spotify_user_id": record.spotify_user_id,
            }
            _save(data)

    def delete(self, session_id: str) -> None:
        with self._lock:
            data = _load()
            data["tokens"].pop(session_id, None)
            _save(data)


class FileOAuthStateStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def save(self, record: OAuthStateRecord) -> None:
        with self._lock:
            data = _load()
            self._prune(data)
            data["states"][record.state] = {
                "state": record.state,
                "session_id": record.session_id,
                "frontend_origin": record.frontend_origin,
                "redirect_uri": record.redirect_uri,
                "created_at": record.created_at,
                "expires_at": record.expires_at,
            }
            _save(data)

    def pop(self, state: str) -> Optional[OAuthStateRecord]:
        with self._lock:
            data = _load()
            self._prune(data)
            record = data["states"].pop(state, None)
            _save(data)
            if not record:
                return None
            return OAuthStateRecord(**record)

    def _prune(self, data: dict) -> None:
        now = int(time.time())
        expired_states = [
            key
            for key, value in data["states"].items()
            if int(value.get("expires_at") or 0) <= now
        ]
        for key in expired_states:
            data["states"].pop(key, None)
