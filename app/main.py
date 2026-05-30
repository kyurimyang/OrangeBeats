# python -m uvicorn app.main:app --reload
# cd frontend/site && npm run build
# .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_allowed_frontend_origins
from app.routers import feedback, playlist, qa, spotify, youtube
from app.services.spotify_session_service import SpotifySessionService
from app.sessions.file_store import FileOAuthStateStore, FileSpotifyTokenStore

app = FastAPI(title="Orange Beats")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    print(f"[500] {request.method} {request.url} | {type(exc).__name__}: {exc}\n{tb}")
    return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


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

# React 빌드가 있으면 SPA, 없으면 frontend/ 바닐라 JS 테스트 UI로 폴백
_USE_SPA = (DIST_DIR / "index.html").is_file()

if LAB_DIR.is_dir():
    app.mount("/lab", StaticFiles(directory=str(LAB_DIR), html=True), name="lab")
if FIGMA_DIR.is_dir():
    app.mount("/figma", StaticFiles(directory=str(FIGMA_DIR), html=True), name="figma")

_HOME_ASSET_DIRS = (
    DIST_DIR / "assets" / "home",
    FRONTEND_DIR / "site" / "public" / "assets" / "home",
)
_HOWTO_ASSET_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/assets/home/{asset_name}")
async def home_howto_asset(asset_name: str) -> FileResponse:
    """How to use PNG — dist·public 양쪽 탐색, 브라우저 캐시 방지."""
    if asset_name != Path(asset_name).name:
        raise HTTPException(status_code=404, detail="Not found")
    for base in _HOME_ASSET_DIRS:
        candidate = base / asset_name
        if candidate.is_file():
            return FileResponse(candidate, headers=_HOWTO_ASSET_HEADERS)
    raise HTTPException(status_code=404, detail="Not found")


if _USE_SPA and (DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="spa_assets")

if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")


_NO_CACHE_HEADERS = {"Cache-Control": "no-store"}


def _index_response() -> FileResponse:
    if _USE_SPA:
        return FileResponse(DIST_DIR / "index.html", headers=_NO_CACHE_HEADERS)
    return FileResponse(FRONTEND_DIR / "index.html", headers=_NO_CACHE_HEADERS)


def _resolve_static_file(path: str) -> Path | None:
    if not path or path.endswith("/"):
        return None
    root = DIST_DIR if _USE_SPA else FRONTEND_DIR
    candidate = root / path
    return candidate if candidate.is_file() else None


@app.get("/")
async def spa_root() -> FileResponse:
    return _index_response()


@app.get("/result/analysis")
@app.get("/result/created")
@app.get("/result/rating")
async def spa_result_analysis() -> FileResponse:
    return _index_response()


@app.get("/{page}")
async def spa_page(page: str) -> FileResponse:
    static_file = _resolve_static_file(page)
    if static_file is not None:
        return FileResponse(static_file, headers=_NO_CACHE_HEADERS)
    return _index_response()


@app.get("/result/{rest:path}")
async def spa_result_subpaths(rest: str) -> FileResponse:
    return _index_response()
