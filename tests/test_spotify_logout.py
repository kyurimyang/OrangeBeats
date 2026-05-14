import time

from starlette.requests import Request
from starlette.responses import Response

from app.config import SPOTIFY_SESSION_COOKIE_NAME
from app.routers.spotify import spotify_logout
from app.services.spotify_session_service import SpotifySessionService
from app.sessions.memory import InMemoryOAuthStateStore, InMemorySpotifyTokenStore
from app.sessions.models import SpotifyTokenRecord


def _request_with_session(session_id: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/spotify/logout",
            "headers": [(b"cookie", f"{SPOTIFY_SESSION_COOKIE_NAME}={session_id}".encode())],
        }
    )


def test_spotify_logout_clears_saved_token_and_cookie():
    token_store = InMemorySpotifyTokenStore()
    session_service = SpotifySessionService(
        token_store=token_store,
        state_store=InMemoryOAuthStateStore(),
    )
    session_id = "session-123"
    token_store.set(
        SpotifyTokenRecord(
            session_id=session_id,
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=int(time.time()) + 3600,
        )
    )

    response = Response()
    result = spotify_logout(_request_with_session(session_id), response, session_service)

    assert result == {"success": True, "logged_in": False}
    assert token_store.get(session_id) is None
    assert f"{SPOTIFY_SESSION_COOKIE_NAME}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
