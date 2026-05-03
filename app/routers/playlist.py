import time
from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.spotify_session import get_spotify_session_service
from app.services.artist_aliases import apply_saved_artist_aliases, clear_artist_aliases, save_artist_aliases
from app.services.pipeline_service import run_youtube_pipeline
from app.services.spotify_cover import SpotifyCoverUploadError, upload_playlist_cover_image
from app.services.spotify_playlist import analyze_spotify_candidates, create_playlist_from_track_uris
from app.services.spotify_service import SpotifyServiceError, create_playlist_from_songs
from app.services.spotify_session_service import SpotifySessionService
from app.services.youtube_thumbnail import (
    YouTubeThumbnailError,
    get_thumbnail_base64_from_image_url,
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


def _normalize_mode(raw_mode: str) -> str:
    mode = (raw_mode or "text").strip().lower()
    mode = {
        "auto": "text",
        "text_only": "text",
        "ocr_only": "ocr",
        "acr_only": "acr",
    }.get(mode, mode)
    if mode not in {"text", "ocr", "acr"}:
        raise HTTPException(status_code=400, detail="mode must be one of: text, ocr, acr")
    return mode


def _dedupe_pipeline_songs(raw_songs: List[Dict]) -> List[Dict[str, str]]:
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
    return songs


def _playlist_name(title_mode: str, user_playlist_name: str, youtube_title: str) -> str:
    if title_mode == "custom":
        return user_playlist_name or youtube_title or "YouTube 변환 플레이리스트"
    return youtube_title or user_playlist_name or "YouTube 변환 플레이리스트"


def _youtube_thumbnail_url(youtube_result: Dict) -> str:
    video_id = (youtube_result.get("video_id") or "").strip()
    if not video_id:
        return ""
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _require_spotify_access_token(request: Request, session_service: SpotifySessionService) -> str:
    session_id = get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Spotify 로그인이 필요합니다.")
    try:
        return session_service.ensure_valid_access_token(session_id)
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _run_youtube_analysis(youtube_url: str, mode: str) -> tuple[Dict, List[Dict[str, str]], int]:
    analysis_started_at = time.perf_counter()
    youtube_result = run_youtube_pipeline(youtube_url, mode=mode)
    analysis_elapsed_ms = int((time.perf_counter() - analysis_started_at) * 1000)

    if not youtube_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=youtube_result.get("error", "YouTube 분석에 실패했습니다."),
        )

    songs = _dedupe_pipeline_songs(youtube_result.get("songs", []))
    if not songs:
        raise HTTPException(status_code=400, detail="YouTube에서 추출된 곡이 없습니다.")

    return youtube_result, songs, analysis_elapsed_ms


@router.post("/from-youtube")
def create_playlist_from_youtube(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    youtube_url = (payload.get("url") or payload.get("youtube_url") or "").strip()
    title_mode = (payload.get("title_mode") or "youtube").strip().lower()
    user_playlist_name = (payload.get("playlist_name") or "").strip()
    mode = _normalize_mode(payload.get("mode") or "text")
    use_artist_aliases = payload.get("use_artist_aliases", payload.get("use_match_overrides", True)) is not False
    total_started_at = time.perf_counter()

    if not youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")

    access_token = _require_spotify_access_token(request, session_service)
    youtube_result, songs, analysis_elapsed_ms = _run_youtube_analysis(youtube_url, mode)
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    final_playlist_name = _playlist_name(title_mode, user_playlist_name, youtube_title)

    try:
        spotify_started_at = time.perf_counter()
        if use_artist_aliases:
            apply_saved_artist_aliases()
        spotify_result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=final_playlist_name,
            songs=songs,
            playlist_description=f"Created from YouTube: {youtube_title or youtube_url}",
            public=True,
        )
        spotify_elapsed_ms = int((time.perf_counter() - spotify_started_at) * 1000)

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

        total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
        timings = {
            "analysis_elapsed_ms": analysis_elapsed_ms,
            "spotify_elapsed_ms": spotify_elapsed_ms,
            "total_elapsed_ms": total_elapsed_ms,
        }

        return {
            "success": True,
            "message": spotify_result.get("message", ""),
            "youtube_url": youtube_url,
            "youtube_title": youtube_title,
            "title_mode": title_mode,
            "mode": mode,
            "use_artist_aliases": use_artist_aliases,
            "selected_stage": youtube_result.get("selected_stage"),
            "ocr_used": youtube_result.get("ocr_used", False),
            "acr_used": youtube_result.get("acr_used", False),
            "playlist_name": final_playlist_name,
            "extracted_count": len(songs),
            "songs": songs,
            "spotify_result": spotify_result,
            "youtube_result": youtube_result,
            "timings": timings,
            "analysis_elapsed_ms": analysis_elapsed_ms,
            "spotify_elapsed_ms": spotify_elapsed_ms,
            "total_elapsed_ms": total_elapsed_ms,
            "matching_rate": spotify_result.get("matching_rate", 0.0),
            "matched_count": spotify_result.get("matched_count", 0),
            "unmatched_count": spotify_result.get("unmatched_count", 0),
            "low_confidence_count": spotify_result.get("low_confidence_count", 0),
            "cover_upload_status": cover_upload_status,
            "cover_upload_error": cover_upload_error,
        }

    except SpotifyServiceError as exc:
        print("SpotifyServiceError =", str(exc))
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc


@router.post("/analyze-youtube")
def analyze_youtube_for_playlist(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    youtube_url = (payload.get("youtube_url") or payload.get("url") or "").strip()
    title_mode = (payload.get("title_mode") or "youtube").strip().lower()
    user_playlist_name = (payload.get("playlist_name") or "").strip()
    mode = _normalize_mode(payload.get("mode") or "text")
    use_artist_aliases = payload.get("use_artist_aliases", payload.get("use_match_overrides", True)) is not False
    total_started_at = time.perf_counter()

    if not youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")

    access_token = _require_spotify_access_token(request, session_service)
    youtube_result, songs, analysis_elapsed_ms = _run_youtube_analysis(youtube_url, mode)

    try:
        spotify_started_at = time.perf_counter()
        results = analyze_spotify_candidates(
            access_token=access_token,
            songs=songs,
            market="KR",
            use_artist_aliases=use_artist_aliases,
        )
        spotify_elapsed_ms = int((time.perf_counter() - spotify_started_at) * 1000)
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc

    total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    candidate_count = sum(1 for item in results if item.get("matched") and item.get("spotify_uri"))
    needs_review_count = sum(1 for item in results if item.get("confidence_label") in {"mid", "low"})
    failed_count = sum(1 for item in results if item.get("confidence_label") == "failed")

    return {
        "success": True,
        "message": "Spotify 매칭 후보를 찾았습니다.",
        "playlist_name": _playlist_name(title_mode, user_playlist_name, youtube_title),
        "youtube_title": youtube_title,
        "thumbnail_url": _youtube_thumbnail_url(youtube_result),
        "title_mode": title_mode,
        "mode": mode,
        "use_artist_aliases": use_artist_aliases,
        "selected_stage": youtube_result.get("selected_stage"),
        "ocr_used": youtube_result.get("ocr_used", False),
        "acr_used": youtube_result.get("acr_used", False),
        "extracted_count": len(songs),
        "spotify_candidate_count": candidate_count,
        "candidate_count": candidate_count,
        "needs_review_count": needs_review_count,
        "failed_count": failed_count,
        "results": results,
        "songs": songs,
        "youtube_result": youtube_result,
        "timings": {
            "analysis_elapsed_ms": analysis_elapsed_ms,
            "spotify_elapsed_ms": spotify_elapsed_ms,
            "total_elapsed_ms": total_elapsed_ms,
        },
        "analysis_elapsed_ms": analysis_elapsed_ms,
        "spotify_elapsed_ms": spotify_elapsed_ms,
        "total_elapsed_ms": total_elapsed_ms,
    }


@router.post("/create-selected")
def create_playlist_from_selected_tracks(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    playlist_name = (payload.get("playlist_name") or "YouTube 변환 플레이리스트").strip()
    description = (payload.get("description") or "").strip()
    thumbnail_url = (payload.get("thumbnail_url") or "").strip()
    track_uris = payload.get("track_uris") or []
    selected_matches = payload.get("selected_matches") or []

    if not isinstance(track_uris, list):
        raise HTTPException(status_code=400, detail="track_uris must be a list")

    unique_track_uris = []
    seen = set()
    for uri in track_uris:
        normalized = (str(uri) if uri is not None else "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_track_uris.append(normalized)

    if not unique_track_uris:
        raise HTTPException(status_code=400, detail="선택된 곡이 없습니다.")

    access_token = _require_spotify_access_token(request, session_service)
    try:
        result = create_playlist_from_track_uris(
            access_token=access_token,
            playlist_name=playlist_name,
            track_uris=unique_track_uris,
            playlist_description=description,
            public=True,
        )
        result["cover_upload_status"] = "not_attempted"
        result["cover_upload_error"] = None
        if thumbnail_url and result.get("playlist_id"):
            try:
                image_base64 = get_thumbnail_base64_from_image_url(thumbnail_url)
                upload_playlist_cover_image(
                    access_token=access_token,
                    playlist_id=result["playlist_id"],
                    image_base64=image_base64,
                )
                result["cover_upload_status"] = "success"
            except (YouTubeThumbnailError, SpotifyCoverUploadError, Exception) as exc:
                result["cover_upload_status"] = "failed"
                result["cover_upload_error"] = str(exc)
        if isinstance(selected_matches, list):
            result["saved_artist_alias_count"] = save_artist_aliases(selected_matches)
        else:
            result["saved_artist_alias_count"] = 0
        return result
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc


@router.delete("/artist-aliases")
def delete_artist_aliases():
    deleted_count = clear_artist_aliases()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": "저장된 사용자 확정 artist alias를 초기화했습니다.",
    }
