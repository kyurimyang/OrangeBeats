import time
from typing import Optional

from app.clients.supabase_client import get_supabase
from app.sessions.models import OAuthStateRecord, SpotifyTokenRecord


class SupabaseSpotifyTokenStore:
    def get(self, session_id: str) -> Optional[SpotifyTokenRecord]:
        result = (
            get_supabase()
            .table("spotify_tokens")
            .select("*")
            .eq("session_id", session_id)
            .maybe_single()
            .execute()
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
        get_supabase().table("spotify_tokens").upsert(data).execute()

    def delete(self, session_id: str) -> None:
        get_supabase().table("spotify_tokens").delete().eq("session_id", session_id).execute()


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
        get_supabase().table("spotify_oauth_states").upsert(data).execute()

    def pop(self, state: str) -> Optional[OAuthStateRecord]:
        self._prune()
        result = (
            get_supabase()
            .table("spotify_oauth_states")
            .select("*")
            .eq("state", state)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return None
        get_supabase().table("spotify_oauth_states").delete().eq("state", state).execute()
        return OAuthStateRecord(**result.data)

    def _prune(self) -> None:
        now = int(time.time())
        get_supabase().table("spotify_oauth_states").delete().lte("expires_at", now).execute()
