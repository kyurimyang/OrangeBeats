from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import youtube
#PowerShell 코드 터미널에 입력하면 YouTube API 호출 테스트 실행 가능
#$line = Get-Content .env | Where-Object { $_ -match '^YOUTUBE_API_KEY=' } | Select-Object -First 1
#$env:YOUTUBE_API_KEY = ($line -split '=', 2)[1].Trim()
#(Invoke-RestMethod "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=1&q=music&key=$env:YOUTUBE_API_KEY").items[0].snippet.title


#터미널에 .\.venv\Scripts\python -m uvicorn backend.main:app --reload 입력하면 서버 실행 가능
app = FastAPI(title = "Orange Caramel Playlist")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube.router)