import time
from typing import Optional

import httpx

from app.clients.supabase_client import get_supabase, reset_supabase
from app.sessions.models import OAuthStateRecord, SpotifyTokenRecord


def _run(build_query):
    """Supabase 쿼리 실행 — HTTP/2 커넥션 끊김 시 클라이언트를 재생성해 1회 재시도."""
    for attempt in range(2):
        try:
            return build_query(get_supabase()).execute()
        except httpx.RemoteProtocolError:
            if attempt == 0:
                reset_supabase()
            else:
                raise


class SupabaseSpotifyTokenStore:
    def get(self, session_id: str) -> Optional[SpotifyTokenRecord]:
        result = _run(
            lambda sb: sb.table("spotify_tokens").select("*").eq("session_id", session_id).maybe_single()
        )
        if not result or not result.data:
            return None
        return SpotifyTokenRecord(**result.data)

    def set(self, record: SpotifyTokenRecord) -> None:
        data = {
            "session_id": record.session_id,
            "access_token": record.access_token,
            "refresh_token": record.refresh_token,
            "expires_at": record.expires_at,
            "spotify_user_id": record.spotify_user_id,
        }
        _run(lambda sb: sb.table("spotify_tokens").upsert(data))

    def delete(self, session_id: str) -> None:
        _run(lambda sb: sb.table("spotify_tokens").delete().eq("session_id", session_id))


class SupabaseOAuthStateStore:
    def save(self, record: OAuthStateRecord) -> None:
        self._prune()
        data = {
            "state": record.state,
            "session_id": record.session_id,
            "frontend_origin": record.frontend_origin,
            "redirect_uri": record.redirect_uri,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
        }
        _run(lambda sb: sb.table("spotify_oauth_states").upsert(data))

    def pop(self, state: str) -> Optional[OAuthStateRecord]:
        self._prune()
        result = _run(
            lambda sb: sb.table("spotify_oauth_states").select("*").eq("state", state).maybe_single()
        )
        if not result or not result.data:
            return None
        _run(lambda sb: sb.table("spotify_oauth_states").delete().eq("state", state))
        return OAuthStateRecord(**result.data)

    def _prune(self) -> None:
        now = int(time.time())
        _run(lambda sb: sb.table("spotify_oauth_states").delete().lte("expires_at", now))
