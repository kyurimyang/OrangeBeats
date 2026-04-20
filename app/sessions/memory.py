import threading
import time
from typing import Optional

from app.sessions.models import OAuthStateRecord, SpotifyTokenRecord


class InMemorySpotifyTokenStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, SpotifyTokenRecord] = {}

    def get(self, session_id: str) -> Optional[SpotifyTokenRecord]:
        with self._lock:
            return self._records.get(session_id)

    def set(self, record: SpotifyTokenRecord) -> None:
        with self._lock:
            self._records[record.session_id] = record

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._records.pop(session_id, None)


class InMemoryOAuthStateStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, OAuthStateRecord] = {}

    def save(self, record: OAuthStateRecord) -> None:
        with self._lock:
            self._prune()
            self._records[record.state] = record

    def pop(self, state: str) -> Optional[OAuthStateRecord]:
        with self._lock:
            self._prune()
            return self._records.pop(state, None)

    def _prune(self) -> None:
        now = int(time.time())
        expired_states = [key for key, value in self._records.items() if value.expires_at <= now]
        for key in expired_states:
            self._records.pop(key, None)
