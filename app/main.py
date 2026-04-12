#서버 시작 파일python -m uvicorn app.main:app --reload
# ``
# 서버 종료 Ctrl + C

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import youtube,spotify,playlist

app = FastAPI(title="Orange Beats")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube.router)
app.include_router(spotify.router)
app.include_router(playlist.router)
