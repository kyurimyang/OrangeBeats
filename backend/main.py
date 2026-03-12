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

app = FastAPI()

@app.get("/")
def root():
    return {"message": "server running"}

@app.get("/health")
def health():
    return {"ok": True}