#서버 시작 파일
# `python -m uvicorn app.main:app --reload`
# 서버 종료 Ctrl + C

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import youtube
from app.routers import spotify

app = FastAPI(title="Orange Beats")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube.router)
app.include_router(spotify.router)
