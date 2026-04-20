#python -m uvicorn app.main:app --reload
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_allowed_frontend_origins
from app.routers import playlist, spotify, youtube
from app.services.spotify_session_service import SpotifySessionService
from app.sessions.memory import InMemoryOAuthStateStore, InMemorySpotifyTokenStore

app = FastAPI(title="Orange Beats")

app.state.spotify_session_service = SpotifySessionService(
    token_store=InMemorySpotifyTokenStore(),
    state_store=InMemoryOAuthStateStore(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(get_allowed_frontend_origins()),
    allow_origin_regex=r"^https?://(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube.router)
app.include_router(spotify.router)
app.include_router(playlist.router)
