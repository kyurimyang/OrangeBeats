#python -m uvicorn app.main:app --reload
#.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

# Next.js static export lives in orangebeats/out/ after `npm run build`.
# Mount /_next first so asset requests don't fall into the catch-all.
STATIC_DIR = Path("orangebeats/out")
if (STATIC_DIR / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=str(STATIC_DIR / "_next")), name="next_assets")


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return JSONResponse({"service": "Orange Beats API", "note": "Run 'npm run build' in orangebeats/ to serve the UI here."})


@app.get("/{path:path}")
async def catch_all(path: str):
    # 1. Exact file match (e.g. favicon.ico, images)
    candidate = STATIC_DIR / path
    if candidate.is_file():
        return FileResponse(str(candidate))
    # 2. Next.js page: url → url.html
    html_file = STATIC_DIR / f"{path}.html"
    if html_file.is_file():
        return FileResponse(str(html_file))
    # 3. SPA fallback
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return JSONResponse({"error": "not found"}, status_code=404)
