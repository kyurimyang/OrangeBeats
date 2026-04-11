from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.routers.spotify import spotify_token_store
from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
)
from app.services.pipeline_service import run_youtube_pipeline
from app.services.spotify_cover import (
    SpotifyCoverUploadError,
    upload_playlist_cover_image,
)
from app.services.youtube_thumbnail import (
    YouTubeThumbnailError,
    get_thumbnail_base64_from_youtube_url,
)
router = APIRouter(prefix="/playlist", tags=["Playlist"])


@router.post("/from-youtube")
def create_playlist_from_youtube(payload: Dict):
    """
    요청 body 예시

    1) 유튜브 제목 그대로 사용 + 자동 fallback
    {
      "url": "https://www.youtube.com/watch?v=xxxxxxx",
      "title_mode": "youtube",
      "mode": "auto"
    }

    2) 직접 입력 제목 사용
    {
      "url": "https://www.youtube.com/watch?v=xxxxxxx",
      "title_mode": "custom",
      "playlist_name": "내 플레이리스트 제목",
      "mode": "auto"
    }

    3) 텍스트만 테스트
    {
      "url": "https://www.youtube.com/watch?v=xxxxxxx",
      "title_mode": "youtube",
      "mode": "text_only"
    }

    4) OCR만 테스트
    {
      "url": "https://www.youtube.com/watch?v=xxxxxxx",
      "title_mode": "youtube",
      "mode": "ocr_only"
    }
    """
    youtube_url = (payload.get("url") or "").strip()
    title_mode = (payload.get("title_mode") or "youtube").strip().lower()
    user_playlist_name = (payload.get("playlist_name") or "").strip()
    mode = (payload.get("mode") or "auto").strip().lower()

    allowed_modes = {"auto", "text_only", "ocr_only"}
    if mode not in allowed_modes:
        mode = "auto"

    if not youtube_url:
        raise HTTPException(status_code=400, detail="url이 필요합니다.")

    access_token = spotify_token_store.get("latest_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Spotify 로그인이 먼저 필요합니다.")

    # 1) 유튜브 분석
    youtube_result = run_youtube_pipeline(youtube_url, mode=mode)

    if not youtube_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=youtube_result.get("error", "유튜브 분석에 실패했습니다.")
        )

    raw_songs = youtube_result.get("songs", [])
    youtube_title = (youtube_result.get("youtube_title") or "").strip()

    if not raw_songs:
        raise HTTPException(status_code=400, detail="유튜브에서 추출된 곡이 없습니다.")

    # 2) Spotify 입력 형식으로 정리
    songs: List[Dict[str, str]] = []
    for item in raw_songs:
        artist = (item.get("artist") or "").strip()
        title = (item.get("title") or "").strip()

        if not title:
            continue

        songs.append({
            "artist": artist,
            "title": title,
        })

    if not songs:
        raise HTTPException(status_code=400, detail="Spotify로 넘길 수 있는 곡 데이터가 없습니다.")

    # 3) 제목 결정
    # - youtube: 유튜브 제목 우선
    # - custom: 사용자가 직접 입력한 제목 우선
    if title_mode == "custom":
        final_playlist_name = user_playlist_name or youtube_title or "유튜브 변환 플레이리스트"
    else:
        final_playlist_name = youtube_title or user_playlist_name or "유튜브 변환 플레이리스트"

    print("=== /playlist/from-youtube called ===")
    print("youtube_url =", youtube_url)
    print("title_mode =", title_mode)
    print("mode =", mode)
    print("youtube_title =", youtube_title)
    print("final_playlist_name =", final_playlist_name)
    print("selected_stage =", youtube_result.get("selected_stage"))
    print("ocr_used =", youtube_result.get("ocr_used"))
    print("extracted songs count =", len(songs))
    print("songs sample =", songs[:3])

   # 4) Spotify 플레이리스트 생성
    try:
        spotify_result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=final_playlist_name,
            songs=songs,
            playlist_description=f"Created from YouTube: {youtube_title or youtube_url}",
            public=True,
        )

        # 5) 유튜브 썸네일 자동 커버 업로드
        cover_upload_status = "not_attempted"
        cover_upload_error = None

        playlist_id = spotify_result.get("playlist_id")

        if playlist_id:
            try:
                image_base64 = get_thumbnail_base64_from_youtube_url(youtube_url)
                upload_playlist_cover_image(
                    access_token=access_token,
                    playlist_id=playlist_id,
                    image_base64=image_base64,
                )
                cover_upload_status = "success"
            except (YouTubeThumbnailError, SpotifyCoverUploadError, Exception) as e:
                # 커버 업로드 실패가 전체 플레이리스트 생성 실패가 되면 안 됨
                cover_upload_status = "failed"
                cover_upload_error = str(e)
                print("cover upload failed =", str(e))
        else:
            cover_upload_status = "failed"
            cover_upload_error = "spotify_result에 playlist_id가 없습니다."
            print("cover upload skipped: playlist_id missing")

        return {
            "success": True,
            "youtube_url": youtube_url,
            "youtube_title": youtube_title,
            "title_mode": title_mode,
            "mode": mode,
            "selected_stage": youtube_result.get("selected_stage"),
            "ocr_used": youtube_result.get("ocr_used", False),
            "playlist_name": final_playlist_name,
            "extracted_count": len(songs),
            "songs": songs,
            "spotify_result": spotify_result,
            "youtube_result": youtube_result,
            "cover_upload_status": cover_upload_status,
            "cover_upload_error": cover_upload_error,
        }

    except SpotifyServiceError as e:
        print("SpotifyServiceError =", str(e))
        raise HTTPException(status_code=500, detail=str(e))