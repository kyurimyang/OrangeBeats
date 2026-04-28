from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.spotify_session import get_spotify_session_service
from app.services.pipeline_service import run_youtube_pipeline
from app.services.spotify_cover import SpotifyCoverUploadError, upload_playlist_cover_image
from app.services.spotify_service import SpotifyServiceError, create_playlist_from_songs
from app.services.spotify_session_service import SpotifySessionService
from app.services.youtube_thumbnail import (
    YouTubeThumbnailError,
    get_thumbnail_base64_from_youtube_url,
)
from app.sessions.session_id import get_session_id

router = APIRouter(prefix="/playlist", tags=["Playlist"])
SpotifySessionDep = Annotated[SpotifySessionService, Depends(get_spotify_session_service)]


def _spotify_http_status(exc: SpotifyServiceError) -> int:
    message = str(exc)
    if "429" in message or "Too many requests" in message or "rate limit" in message.lower():
        return 429
    return 500


@router.post("/from-youtube")
def create_playlist_from_youtube(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    youtube_url = (payload.get("url") or "").strip()
    title_mode = (payload.get("title_mode") or "youtube").strip().lower()
    user_playlist_name = (payload.get("playlist_name") or "").strip()
    mode = (payload.get("mode") or "auto").strip().lower()

    allowed_modes = {"auto", "text_only", "ocr_only"}
    if mode not in allowed_modes:
        mode = "auto"

    if not youtube_url:
        raise HTTPException(status_code=400, detail="url이 필요합니다.")

    session_id = get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Spotify 로그인 세션이 없습니다.")

    try:
        access_token = session_service.ensure_valid_access_token(session_id)
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    youtube_result = run_youtube_pipeline(youtube_url, mode=mode)

    if not youtube_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=youtube_result.get("error", "유튜브 분석에 실패했습니다."),
        )

    raw_songs = youtube_result.get("songs", [])
    youtube_title = (youtube_result.get("youtube_title") or "").strip()

    if not raw_songs:
        raise HTTPException(status_code=400, detail="유튜브에서 추출된 곡이 없습니다.")

    songs: List[Dict[str, str]] = []
    seen = set()
    for item in raw_songs:
        artist = (item.get("artist") or "").strip()
        title = (item.get("title") or "").strip()
        if not title:
            continue
        key = (artist.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        songs.append(
            {
                "artist": artist,
                "title": title,
                "raw": item.get("raw", ""),
                "left": item.get("left", ""),
                "right": item.get("right", ""),
                "swap_applied": item.get("swap_applied", False),
                "global_direction": item.get("global_direction", "per_line"),
                "chosen_case": item.get("chosen_case", "original"),
                "score": item.get("score", 0.0),
                "reason": item.get("reason", ""),
                "swap_guard_applied": item.get("swap_guard_applied", False),
                "swap_guard_reason": item.get("swap_guard_reason", ""),
            }
        )

    if not songs:
        raise HTTPException(status_code=400, detail="Spotify로 넘길 수 있는 곡 데이터가 없습니다.")

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

    try:
        spotify_result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=final_playlist_name,
            songs=songs,
            playlist_description=f"Created from YouTube: {youtube_title or youtube_url}",
            public=True,
        )

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
            except (YouTubeThumbnailError, SpotifyCoverUploadError, Exception) as exc:
                cover_upload_status = "failed"
                cover_upload_error = str(exc)
                print("cover upload failed =", str(exc))
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

    except SpotifyServiceError as exc:
        print("SpotifyServiceError =", str(exc))
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc))
