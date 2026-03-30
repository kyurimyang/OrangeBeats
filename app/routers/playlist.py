from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.routers.spotify import spotify_token_store
from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
)
from app.services.pipeline_service import run_youtube_text_pipeline

router = APIRouter(prefix="/playlist", tags=["Playlist"])


@router.post("/from-youtube")
def create_playlist_from_youtube(payload: Dict):
    """
    요청 body 예시
    {
      "url": "https://www.youtube.com/watch?v=xxxxxxx",
      "playlist_name": "유튜브 변환 플레이리스트"
    }
    """
    youtube_url = payload.get("url")
    playlist_name = payload.get("playlist_name", "유튜브 변환 플레이리스트")

    if not youtube_url:
        raise HTTPException(status_code=400, detail="url이 필요합니다.")

    access_token = spotify_token_store.get("latest_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Spotify 로그인이 먼저 필요합니다.")

    # 1) 유튜브 분석
    youtube_result = run_youtube_text_pipeline(youtube_url)

    if not youtube_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=youtube_result.get("error", "유튜브 분석에 실패했습니다.")
        )

    raw_songs = youtube_result.get("songs", [])
    if not raw_songs:
        raise HTTPException(status_code=400, detail="유튜브에서 추출된 곡이 없습니다.")

    # 2) Spotify 입력 형식으로 정리
    songs: List[Dict[str, str]] = []
    for item in raw_songs:
        title = (item.get("title") or "").strip()
        artist = (item.get("artist") or "").strip()

        if not title:
            continue

        songs.append({
            "title": title,
            "artist": artist,
        })

    if not songs:
        raise HTTPException(status_code=400, detail="Spotify로 넘길 수 있는 곡 데이터가 없습니다.")

    print("=== /playlist/from-youtube called ===")
    print("youtube_url =", youtube_url)
    print("playlist_name =", playlist_name)
    print("extracted songs count =", len(songs))
    print("songs sample =", songs[:3])

    # 3) Spotify 플레이리스트 생성
    try:
        spotify_result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=playlist_name,
            songs=songs,
            playlist_description="Created from YouTube playlist text",
            public=True,
        )

        return {
            "success": True,
            "youtube_url": youtube_url,
            "playlist_name": playlist_name,
            "extracted_count": len(songs),
            "songs": songs,
            "spotify_result": spotify_result,
        }

    except SpotifyServiceError as e:
        print("SpotifyServiceError =", str(e))
        raise HTTPException(status_code=500, detail=str(e))