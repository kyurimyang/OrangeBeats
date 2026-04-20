from fastapi import Request

from app.services.spotify_session_service import SpotifySessionService


def get_spotify_session_service(request: Request) -> SpotifySessionService:
    return request.app.state.spotify_session_service
