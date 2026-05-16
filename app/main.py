#python -m uvicorn app.main:app --reload
#.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
import importlib
import importlib.util
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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-Id"],
)

app.include_router(youtube.router)
app.include_router(spotify.router)
app.include_router(playlist.router)
app.include_router(qa.router)

# feedback 라우터: UI_MERGE_FRONTEND 병합 후 자동 활성화
_feedback_spec = importlib.util.find_spec("app.routers.feedback")
if _feedback_spec is not None:
    from app.routers import feedback as _feedback_mod
    app.include_router(_feedback_mod.router)

# 프론트엔드 디렉토리: React 빌드(frontend/dist)가 있으면 우선 사용, 없으면 바닐라 JS(frontend/)
_DIST_DIR = Path("frontend/dist")
_VANILLA_DIR = Path("frontend")
FRONTEND_DIR = _DIST_DIR if _DIST_DIR.is_dir() and (_DIST_DIR / "index.html").is_file() else _VANILLA_DIR

LAB_DIR = _VANILLA_DIR / "lab"
FIGMA_DIR = _VANILLA_DIR / "figma"

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
