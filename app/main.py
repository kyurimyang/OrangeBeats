#python -m uvicorn app.main:app --reload
#.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_allowed_frontend_origins
from app.routers import playlist, qa, spotify, youtube
from app.services.spotify_session_service import SpotifySessionService
from app.sessions.file_store import FileOAuthStateStore, FileSpotifyTokenStore

app = FastAPI(title="Orange Beats")

app.state.spotify_session_service = SpotifySessionService(
    token_store=FileSpotifyTokenStore(),
    state_store=FileOAuthStateStore(),
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
app.include_router(qa.router)

FRONTEND_DIR = Path("frontend")
LAB_DIR = FRONTEND_DIR / "lab"
FIGMA_DIR = FRONTEND_DIR / "figma"

if LAB_DIR.is_dir():
    app.mount("/lab", StaticFiles(directory=str(LAB_DIR), html=True), name="lab")
if FIGMA_DIR.is_dir():
    app.mount("/figma", StaticFiles(directory=str(FIGMA_DIR), html=True), name="figma")

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/{path:path}")
async def catch_all(path: str) -> FileResponse:
    candidate = FRONTEND_DIR / path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(FRONTEND_DIR / "index.html"))
