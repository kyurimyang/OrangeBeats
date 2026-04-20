import time
from typing import Optional

from app.sessions.models import OAuthStateRecord, SpotifyTokenRecord
from app.services.spotify_auth import refresh_access_token
from app.services.spotify_exceptions import SpotifyServiceError

AUTH_STATE_TTL_SECONDS = 600


class SpotifySessionService:
    def __init__(self, token_store, state_store) -> None:
        self._token_store = token_store
        self._state_store = state_store

    def save_auth_state(
        self,
        *,
        state: str,
        session_id: str,
        frontend_origin: str,
        redirect_uri: str,
    ) -> None:
        now = int(time.time())
        self._state_store.save(
            OAuthStateRecord(
                state=state,
                session_id=session_id,
                frontend_origin=frontend_origin,
                redirect_uri=redirect_uri,
                created_at=now,
                expires_at=now + AUTH_STATE_TTL_SECONDS,
            )
        )

    def pop_auth_state(self, state: str) -> Optional[OAuthStateRecord]:
        return self._state_store.pop(state)

    def save_token_data(self, session_id: str, token_data: dict) -> None:
        current_record = self._token_store.get(session_id)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token") or (
            current_record.refresh_token if current_record else None
        )
        expires_in = int(token_data.get("expires_in") or 3600)

        if not access_token:
            raise SpotifyServiceError("Spotify access token이 없습니다.")

        self._token_store.set(
            SpotifyTokenRecord(
                session_id=session_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=int(time.time()) + max(60, expires_in - 90),
            )
        )

    def clear_tokens(self, session_id: str) -> None:
        self._token_store.delete(session_id)

    def get_refresh_token(self, session_id: str) -> Optional[str]:
        record = self._token_store.get(session_id)
        return record.refresh_token if record else None

    def get_access_token(self, session_id: str) -> Optional[str]:
        record = self._token_store.get(session_id)
        return record.access_token if record else None

    def is_logged_in(self, session_id: str) -> bool:
        record = self._token_store.get(session_id)
        return bool(record and (record.access_token or record.refresh_token))

    def ensure_valid_access_token(self, session_id: str) -> str:
        record = self._token_store.get(session_id)
        now = int(time.time())

        if record and record.access_token and now < record.expires_at:
            return record.access_token

        refresh_token = record.refresh_token if record else None
        if not refresh_token:
            raise SpotifyServiceError("Spotify 로그인이 필요합니다. 다시 로그인해 주세요.")

        refreshed = refresh_access_token(refresh_token)
        if refresh_token and not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = refresh_token
        self.save_token_data(session_id, refreshed)

        updated = self._token_store.get(session_id)
        if not updated or not updated.access_token:
            raise SpotifyServiceError("Spotify access token 갱신에 실패했습니다.")
        return updated.access_token
