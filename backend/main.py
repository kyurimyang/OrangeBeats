import os
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

# env.example -> .env로 이름 바꾸고 API키 값 넣은 다음에
# 터미널에 python -m uvicorn backend.main:app --reload 입력해서 제대로 했는지 확인햐시길
# 터미널 단축키 Ctrl + `

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

print("OPENAI loaded:", bool(OPENAI_API_KEY))
print("YOUTUBE loaded:", bool(YOUTUBE_API_KEY))
print("SPOTIFY CLIENT ID loaded:", bool(SPOTIFY_CLIENT_ID))
print("SPOTIFY CLIENT SECRET loaded:", bool(SPOTIFY_CLIENT_SECRET))

#PowerShell 코드 터미널에 입력하면 YouTube API 호출 테스트 실행 가능
#$line = Get-Content .env | Where-Object { $_ -match '^YOUTUBE_API_KEY=' } | Select-Object -First 1
#$env:YOUTUBE_API_KEY = ($line -split '=', 2)[1].Trim()
#(Invoke-RestMethod "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=1&q=music&key=$env:YOUTUBE_API_KEY").items[0].snippet.title


#터미널에 .\.venv\Scripts\python -m uvicorn backend.main:app --reload 입력하면 서버 실행 가능
app = FastAPI()

@app.get("/")
def root():
    return {"message": "server running"}

@app.get("/health")
def health():
    return {"ok": True}
