# python -m uvicorn app.main:app --reload
# .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_allowed_frontend_origins
from app.routers import feedback, playlist, qa, spotify, youtube
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
app.include_router(feedback.router)

FRONTEND_DIR = Path("frontend")
DIST_DIR = FRONTEND_DIR / "dist"
LAB_DIR = FRONTEND_DIR / "lab"
FIGMA_DIR = FRONTEND_DIR / "figma"

if LAB_DIR.is_dir():
    app.mount("/lab", StaticFiles(directory=str(LAB_DIR), html=True), name="lab")
if FIGMA_DIR.is_dir():
    app.mount("/figma", StaticFiles(directory=str(FIGMA_DIR), html=True), name="figma")

if (DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="spa_assets")

if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")


_NO_CACHE_HEADERS = {"Cache-Control": "no-store"}


def _spa_index_response() -> FileResponse:
    index_file = DIST_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=503, detail="Frontend build is missing. Run npm run build in frontend/site.")
    return FileResponse(index_file, headers=_NO_CACHE_HEADERS)


def _resolve_spa_file(path: str) -> Path | None:
    if not path or path.endswith("/"):
        return None
    candidate = DIST_DIR / path
    if candidate.is_file():
        return candidate
    return None


@app.get("/")
async def spa_root() -> FileResponse:
    return _spa_index_response()


@app.get("/result/analysis")
@app.get("/result/created")
@app.get("/result/rating")
async def spa_result_analysis() -> FileResponse:
    return _spa_index_response()


@app.get("/{page}")
async def spa_page(page: str) -> FileResponse:
    static_file = _resolve_spa_file(page)
    if static_file is not None:
        return FileResponse(static_file, headers=_NO_CACHE_HEADERS)

    return _spa_index_response()


@app.get("/result/{rest:path}")
async def spa_result_subpaths(rest: str) -> FileResponse:
    return _spa_index_response()
