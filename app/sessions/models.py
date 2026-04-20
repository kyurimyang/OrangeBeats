from dataclasses import dataclass
from typing import Optional


@dataclass
class SpotifyTokenRecord:
    session_id: str
    access_token: str
    refresh_token: Optional[str]
    expires_at: int
    spotify_user_id: Optional[str] = None


@dataclass
class OAuthStateRecord:
    state: str
    session_id: str
    frontend_origin: str
    redirect_uri: str
    created_at: int
    expires_at: int
