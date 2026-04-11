import secrets
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
    exchange_code_for_token,
    get_spotify_login_url,
)

router = APIRouter(prefix="/spotify", tags=["Spotify"])

# 실제 배포에서는 DB/Redis/세션으로 바꾸기
spotify_auth_state_store = {}
spotify_token_store = {}


@router.get("/login")
def spotify_login():
    state = secrets.token_urlsafe(16)
    spotify_auth_state_store[state] = True

    login_url = get_spotify_login_url(state=state)

    return {
        "login_url": login_url,
        "state": state,
    }


@router.get("/callback")
def spotify_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    if state not in spotify_auth_state_store:
        raise HTTPException(status_code=400, detail="유효하지 않은 state입니다.")

    try:
        token_data = exchange_code_for_token(code)

        print("=== /spotify/callback called ===")
        print("callback state =", state)
        print("token_data =", token_data)
        print("granted scope =", token_data.get("scope"))

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")

        spotify_token_store["latest_access_token"] = access_token
        if refresh_token:
            spotify_token_store["latest_refresh_token"] = refresh_token

        # state는 검증용으로만 썼으니 사용 후 제거
        spotify_auth_state_store.pop(state, None)

        print("latest access token saved =", bool(spotify_token_store.get("latest_access_token")))
        print("latest refresh token saved =", bool(spotify_token_store.get("latest_refresh_token")))

        return {
            "message": "Spotify 로그인 성공",
            "access_token_saved": True,
            "refresh_token_saved": bool(refresh_token),
            "scope": token_data.get("scope"),
        }

    except SpotifyServiceError as e:
        print("SpotifyServiceError =", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-playlist")
def create_spotify_playlist(payload: Dict):
    """
    요청 body 예시
    {
      "playlist_name": "유튜브 추출 플레이리스트",
      "songs": [
        {"artist": "NewJeans", "title": "Ditto"},
        {"artist": "DAY6", "title": "한 페이지가 될 수 있게"}
      ]
    }
    """
    access_token = spotify_token_store.get("latest_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Spotify 로그인이 먼저 필요합니다.")

    print("=== /spotify/create-playlist called ===")
    print("payload =", payload)
    print("token exists =", bool(access_token))

    playlist_name = (payload.get("playlist_name") or "새 플레이리스트").strip()
    songs: List[Dict[str, str]] = payload.get("songs", [])

    print("playlist_name =", playlist_name)
    print("songs count =", len(songs))
    print("songs sample =", songs[:3])

    if not songs:
        raise HTTPException(status_code=400, detail="songs가 비어 있습니다.")

    try:
        result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=playlist_name,
            songs=songs,
            playlist_description="Created from YouTube playlist text",
            public=True,
        )

        return {
            "success": True,
            "result": result,
        }

    except SpotifyServiceError as e:
        print("SpotifyServiceError =", str(e))
        raise HTTPException(status_code=500, detail=str(e))