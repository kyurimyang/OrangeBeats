import time
import math
import json
import re
from pathlib import Path
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.spotify_session import get_spotify_session_service
from app.services.analysis_flow import classify_text_analysis
from app.services.pipeline_service import run_youtube_pipeline
from app.services.spotify_cover import SpotifyCoverUploadError, upload_playlist_cover_image
from app.services.spotify_playlist import (
    analyze_spotify_candidates,
    create_playlist_from_track_uris,
    enrich_results_album_images,
)
from app.services.spotify_service import SpotifyServiceError, create_playlist_from_songs
from app.services.spotify_session_service import SpotifySessionService
from app.services.youtube_thumbnail import (
    extract_playlist_id,
    extract_video_id,
    get_playlist_thumbnail_url,
    YouTubeThumbnailError,
    get_thumbnail_base64_from_image_url,
    get_thumbnail_base64_from_youtube_url,
)
from app.sessions.session_id import get_session_id

from app.ocr.ocr_pipeline import run_ocr_pipeline
from app.services.text_source_builder import build_combined_text

router = APIRouter(prefix="/playlist", tags=["Playlist"])
SpotifySessionDep = Annotated[SpotifySessionService, Depends(get_spotify_session_service)]
DEMO_CACHE_FILE = Path("data/demo_cache.json")


def _json_safe(value: Any, _seen: Any = None) -> Any:
    if _seen is None:
        _seen = set()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        oid = id(value)
        if oid in _seen:
            return {}
        _seen.add(oid)
        result = {str(key): _json_safe(item, _seen) for key, item in value.items()}
        _seen.discard(oid)
        return result
    if isinstance(value, (list, tuple, set)):
        oid = id(value)
        if oid in _seen:
            return []
        _seen.add(oid)
        result = [_json_safe(item, _seen) for item in value]
        _seen.discard(oid)
        return result
    return str(value)


def _load_demo_cache() -> Dict:
    if not DEMO_CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(DEMO_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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
                "source": item.get("source", ""),
                "source_mode": item.get("source_mode", ""),
                "timestamp": item.get("timestamp", ""),
                "raw": item.get("raw", ""),
                "original_input": item.get("original_input", {}),
                "corrected_input": item.get("corrected_input", {}),
                "left": item.get("left", ""),
                "right": item.get("right", ""),
                "swap_applied": item.get("swap_applied", False),
                "global_direction": item.get("global_direction", "per_line"),
                "chosen_case": item.get("chosen_case", "original"),
                "score": item.get("score", 0.0),
                "reason": item.get("reason", ""),
                "swap_guard_applied": item.get("swap_guard_applied", False),
                "swap_guard_reason": item.get("swap_guard_reason", ""),
                "artist_inferred": item.get("artist_inferred", False),
                "inferred_artist_source": item.get("inferred_artist_source", ""),
                "artist_exists": item.get("artist_exists", bool(artist)),
                "title_exists": item.get("title_exists", bool(title)),
                "is_complete": item.get("is_complete", bool(artist and title)),
                "completeness_score": item.get("completeness_score", 1.0 if artist and title else 0.5),
                "confidence": item.get("confidence", item.get("score", 0.0)),
                "sources": item.get("sources", []),
                "title_metadata_hints": item.get("title_metadata_hints", []),
                "title_feature_artists": item.get("title_feature_artists", []),
                "title_producer_artists": item.get("title_producer_artists", []),
                "raw_line": item.get("raw_line", ""),
                "line_index": item.get("line_index", -1),
                "evidence_type": item.get("evidence_type", ""),
                "reject_reason": item.get("reject_reason", ""),
                "acr_spotify_track_id": item.get("acr_spotify_track_id", ""),
                "acr_spotify_artist_ids": item.get("acr_spotify_artist_ids", []),
                "acr_evidence": item.get("acr_evidence", {}),
                "ocr_evidence": item.get("ocr_evidence", {}),
            }
        )
    return songs


def _is_edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True

    left_len = len(left)
    right_len = len(right)
    if abs(left_len - right_len) > 1:
        return False

    edits = 0
    left_index = 0
    right_index = 0
    while left_index < left_len and right_index < right_len:
        if left[left_index] == right[right_index]:
            left_index += 1
            right_index += 1
            continue

        edits += 1
        if edits > 1:
            return False

        if left_len == right_len:
            left_index += 1
            right_index += 1
        elif left_len > right_len:
            left_index += 1
        else:
            right_index += 1

    return True


def _fuzzy_dedup_songs(songs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if len(songs) < 10:
        return songs

    deduped: List[Dict[str, str]] = []
    for song in songs:
        artist = (song.get("artist") or "").strip().casefold()
        title = (song.get("title") or "").strip().casefold()
        if not title:
            continue

        is_duplicate = False
        for existing in deduped:
            existing_artist = (existing.get("artist") or "").strip().casefold()
            existing_title = (existing.get("title") or "").strip().casefold()
            if artist == existing_artist and _is_edit_distance_at_most_one(title, existing_title):
                is_duplicate = True
                break

        if not is_duplicate:
            deduped.append(song)

    return deduped


def _playlist_name(title_mode: str, user_playlist_name: str, youtube_title: str) -> str:
    if title_mode == "custom":
        return user_playlist_name or youtube_title or "YouTube 변환 플레이리스트"
    return youtube_title or user_playlist_name or "YouTube 변환 플레이리스트"


def _youtube_thumbnail_url(youtube_result: Dict) -> str:
    video_id = (youtube_result.get("video_id") or "").strip()
    if video_id:
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

    input_url = (youtube_result.get("input_url") or "").strip()
    playlist_id = extract_playlist_id(input_url)
    if playlist_id:
        return get_playlist_thumbnail_url(playlist_id)

    return ""



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

    songs = _fuzzy_dedup_songs(_dedupe_pipeline_songs(youtube_result.get("songs", [])))
    for song in songs:
        song["source_mode"] = mode
    if not songs:
        raise HTTPException(status_code=400, detail="YouTube에서 추출된 곡이 없습니다.")

    return youtube_result, songs, analysis_elapsed_ms


def _normalize_spotify_track_id(value: Any) -> str:
    s = str(value or "").strip()
    if re.fullmatch(r"[0-9A-Za-z]{22}", s):
        return s
    return ""


def _normalize_spotify_track_uri(value: Any) -> str:
    """track_uris 페이로드 — spotify: URI, open.spotify URL, 22자 track id 모두 허용."""
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith("spotify:track:"):
        return s
    if "open.spotify.com" in s and "/track/" in s:
        m = re.search(r"/(?:intl-[a-z]{2}/)?track/([0-9A-Za-z]{22})", s)
        if m:
            return f"spotify:track:{m.group(1)}"
    tid = _normalize_spotify_track_id(s)
    if tid:
        return f"spotify:track:{tid}"
    return s if s.startswith("spotify:") else ""


def _source_only_candidate(song: Dict[str, Any]) -> Dict:
    artist = (song.get("artist") or "").strip()
    title = (song.get("title") or "").strip()
    acr_tid = _normalize_spotify_track_id(song.get("acr_spotify_track_id"))
    spotify_uri = f"spotify:track:{acr_tid}" if acr_tid else None
    return {
        "input_artist": artist,
        "input_title": title,
        "matched": False,
        "spotify_track_id": acr_tid or None,
        "spotify_uri": spotify_uri,
        "spotify_title": None,
        "spotify_artist": None,
        "album_image": None,
        "confidence": 0,
        "score": 0,
        "final_score": 0,
        "status": "source_only",
        "confidence_label": "failed",
        "reason": ["OCR/텍스트에서 추출된 곡입니다. Spotify 후보 검색은 아직 실행하지 않았습니다."],
        "reason_text": "OCR/텍스트에서 추출된 곡입니다. Spotify 후보 검색은 아직 실행하지 않았습니다.",
        "selected": False,
        "match_status": "unmatched",
        "top_candidates": [],
        "source_only": True,
        "raw": song.get("raw", ""),
    }


def _compact_youtube_result(youtube_result: Dict, songs: List[Dict[str, str]]) -> Dict:
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    debug = youtube_result.get("debug", {}) if isinstance(youtube_result.get("debug"), dict) else {}
    vision_debug = debug.get("vision", {}) if isinstance(debug.get("vision"), dict) else {}
    vision_text = str(vision_debug.get("raw_text") or youtube_result.get("vision_text") or "")
    raw_ocr_text = str(vision_debug.get("raw_ocr_text") or youtube_result.get("ocr_text") or "")
    ocr_blocks = vision_debug.get("ocr_blocks", youtube_result.get("ocr_blocks", []))
    selected_ocr_block = vision_debug.get("selected_ocr_block", youtube_result.get("selected_ocr_block", {}))

    compact = {
        "success": youtube_result.get("success", False),
        "input_url": youtube_result.get("input_url", ""),
        "video_id": youtube_result.get("video_id", ""),
        "youtube_title": youtube_title,
        "selected_stage": youtube_result.get("selected_stage"),
        "text_stage": youtube_result.get("text_stage"),
        "mode": youtube_result.get("mode", ""),
        "ocr_used": youtube_result.get("ocr_used", False),
        "acr_used": youtube_result.get("acr_used", False),
        "songs": songs,
        "failure_reason": youtube_result.get("failure_reason", ""),
        "is_ai_playlist": youtube_result.get("is_ai_playlist", False),
        "is_single_artist": youtube_result.get("is_single_artist", False),
        "inferred_artist": youtube_result.get("inferred_artist", ""),
        "single_artist_detection": youtube_result.get("single_artist_detection", {}),
        "fallback_recommendation": youtube_result.get("fallback_recommendation", {}),
        "signals": youtube_result.get("signals", {}),
        "metrics": youtube_result.get("metrics", {}),
    }

    if vision_text:
        compact["vision_text"] = vision_text
        compact["ocr_text"] = raw_ocr_text or vision_text
        compact["ocr_blocks"] = ocr_blocks
        compact["selected_ocr_block"] = selected_ocr_block
        compact["debug"] = {"vision": vision_debug}
    else:
        compact["debug"] = debug

    return compact


def _make_no_songs_message(mode: str, youtube_result: Dict) -> str:
    if youtube_result.get("is_ai_playlist"):
        return "AI 생성 음악 플레이리스트입니다. Suno, Udio 등 AI가 만든 음악은 Spotify에 등록되어 있지 않아 곡을 찾을 수 없습니다."

    if mode == "acr":
        error = youtube_result.get("error", "")
        if error:
            return f"ACR 오디오 인식 실패: {error}"
        unrecognized = youtube_result.get("unrecognized_reason", "") or (youtube_result.get("signals") or {}).get("unrecognized_reason", "")
        acr_reason_map = {
            "not_in_db": "음원 인식에 실패했습니다. ACR DB에 등록되지 않은 음원이거나 저작권 보호 음원일 수 있습니다.",
            "short_segment": "오디오 세그먼트가 너무 짧아 인식하지 못했습니다.",
            "transition": "전환 구간이 많아 인식률이 낮습니다. 오디오가 명확한 영상에서 시도해보세요.",
            "low_confidence_audio": "오디오 품질이 낮아 인식하지 못했습니다.",
        }
        return acr_reason_map.get(unrecognized, "ACR 오디오 인식에서 곡을 찾지 못했습니다.")

    if mode != "ocr":
        fallback = youtube_result.get("fallback_recommendation", {})
        rec = (fallback or {}).get("recommended_stage", "")
        rec_msg = (fallback or {}).get("message", "")
        if rec:
            return f"텍스트에서 곡을 찾지 못했습니다. {rec_msg} ({rec.upper()} 모드를 시도해보세요)"
        return "description과 댓글에서 곡 목록을 찾지 못했습니다."

    reason_map = {
        "frame_selection_failed": "영상 프레임 추출에 실패했습니다. yt-dlp가 이 영상에 접근할 수 없거나 네트워크 문제일 수 있습니다.",
        "no_text_frame": "모든 프레임에서 텍스트를 인식하지 못했습니다. 트랙리스트가 화면에 없는 영상일 수 있습니다.",
        "low_quality_frame": "화면에서 읽힌 텍스트가 너무 짧습니다. 자막이나 트랙리스트가 작거나 흐릿할 수 있습니다.",
        "ocr_noise_too_high": "텍스트는 인식됐지만 곡 목록 형식을 파악하지 못했습니다. Raw Debug 탭에서 OCR 텍스트를 확인해보세요.",
    }
    failure = youtube_result.get("failure_reason", "")
    return reason_map.get(failure, "OCR에서 곡을 추출하지 못했습니다.")


def _build_analysis_response(
    *,
    youtube_url: str,
    youtube_result: Dict,
    songs: List[Dict[str, str]],
    results: List[Dict],
    title_mode: str,
    user_playlist_name: str,
    mode: str,
    analysis_elapsed_ms: int,
    spotify_elapsed_ms: int,
    total_elapsed_ms: int,
    message: str,
    spotify_error: str = "",
) -> Dict:
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    candidate_count = sum(1 for item in results if item.get("matched") and item.get("spotify_uri"))
    needs_review_count = sum(1 for item in results if item.get("confidence_label") in {"mid", "low"})
    failed_count = sum(1 for item in results if item.get("confidence_label") == "failed")

    matched_tracks = [item for item in results if item.get("matched") and item.get("spotify_uri")]
    unmatched_tracks = [item for item in results if not (item.get("matched") and item.get("spotify_uri"))]

    compact_youtube_result = _compact_youtube_result(youtube_result, songs)

    if spotify_error:
        text_class = classify_text_analysis(youtube_result, songs)
        analysis_state = text_class["analysis_state"]
        needs_fallback = text_class["needs_fallback"]
        next_action = text_class["next_action"]
    elif results:
        analysis_state = "candidates_ready"
        needs_fallback = False
        next_action = "select_tracks"
    elif songs:
        text_class = classify_text_analysis(youtube_result, songs)
        analysis_state = text_class["analysis_state"]
        needs_fallback = text_class["needs_fallback"]
        next_action = text_class["next_action"]
    else:
        analysis_state = "text_failed"
        needs_fallback = True
        next_action = "choose_fallback"

    return {
        "success": not spotify_error,
        "partial_success": bool(youtube_result.get("partial_success")),
        "warning": str(youtube_result.get("warning") or ""),
        "analysis_state": analysis_state,
        "needs_fallback": needs_fallback,
        "next_action": next_action,
        "message": message,
        "playlist_name": _playlist_name(title_mode, user_playlist_name, youtube_title),
        "youtube_url": youtube_url,
        "youtube_title": youtube_title,
        "thumbnail_url": _youtube_thumbnail_url(youtube_result),
        "title_mode": title_mode,
        "mode": mode,
        "selected_stage": youtube_result.get("selected_stage"),
        "ocr_used": youtube_result.get("ocr_used", False),
        "acr_used": youtube_result.get("acr_used", False),
        "is_single_artist": youtube_result.get("is_single_artist", False),
        "inferred_artist": youtube_result.get("inferred_artist", ""),
        "single_artist_detection": youtube_result.get("single_artist_detection", {}),
        "extracted_count": len(songs),
        "spotify_candidate_count": candidate_count,
        "candidate_count": candidate_count,
        "needs_review_count": needs_review_count,
        "failed_count": failed_count,
        "results": results,
        "songs": songs,
        "extracted_songs": songs,
        "matched_tracks": matched_tracks,
        "unmatched_tracks": unmatched_tracks,
        "ocr_text": compact_youtube_result.get("ocr_text", compact_youtube_result.get("vision_text", "")),
        "ocr_blocks": compact_youtube_result.get("ocr_blocks", []),
        "selected_ocr_block": compact_youtube_result.get("selected_ocr_block", {}),
        "youtube_result": compact_youtube_result,
        "spotify_error": spotify_error,
        "debug": {
            "youtube": compact_youtube_result.get("debug", {}),
            "selected_stage": youtube_result.get("selected_stage"),
            "spotify_error": spotify_error,
        },
        "timings": {
            "analysis_elapsed_ms": analysis_elapsed_ms,
            "spotify_elapsed_ms": spotify_elapsed_ms,
            "total_elapsed_ms": total_elapsed_ms,
        },
        "analysis_elapsed_ms": analysis_elapsed_ms,
        "spotify_elapsed_ms": spotify_elapsed_ms,
        "total_elapsed_ms": total_elapsed_ms,
    }


def _build_ocr_preview_response(
    *,
    youtube_url: str,
    youtube_result: Dict,
    songs: List[Dict[str, str]],
    title_mode: str,
    user_playlist_name: str,
    mode: str,
    analysis_elapsed_ms: int,
    total_elapsed_ms: int,
    message: str,
) -> Dict:
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    results = [_source_only_candidate(song) for song in songs]
    debug = youtube_result.get("debug", {}) if isinstance(youtube_result.get("debug"), dict) else {}
    vision_debug = debug.get("vision", {}) if isinstance(debug.get("vision"), dict) else {}
    vision_text = str(vision_debug.get("raw_text") or youtube_result.get("vision_text") or "")

    partial_success = bool(youtube_result.get("partial_success"))
    warning = str(youtube_result.get("warning") or "")
    if songs:
        ocr_state = "fallback_success"
        ocr_needs_fallback = False
        ocr_next_action = "match_candidates"
    else:
        ocr_state = "fallback_failed"
        ocr_needs_fallback = True
        ocr_next_action = "choose_fallback"
    return {
        "success": True,
        "partial_success": partial_success,
        "warning": warning,
        "analysis_state": ocr_state,
        "needs_fallback": ocr_needs_fallback,
        "next_action": ocr_next_action,
        "message": message,
        "playlist_name": _playlist_name(title_mode, user_playlist_name, youtube_title),
        "youtube_url": youtube_url,
        "youtube_title": youtube_title,
        "title_mode": title_mode,
        "mode": mode,
        "selected_stage": youtube_result.get("selected_stage"),
        "ocr_used": True,
        "acr_used": False,
        "is_single_artist": youtube_result.get("is_single_artist", False),
        "inferred_artist": youtube_result.get("inferred_artist", ""),
        "single_artist_detection": youtube_result.get("single_artist_detection", {}),
        "extracted_count": len(songs),
        "spotify_candidate_count": 0,
        "candidate_count": 0,
        "needs_review_count": 0,
        "failed_count": len(results),
        "results": results,
        "songs": songs,
        "extracted_songs": songs,
        "matched_tracks": [],
        "unmatched_tracks": results,
        "ocr_text": vision_text,
        "ocr_blocks": vision_debug.get("ocr_blocks", []),
        "selected_ocr_block": vision_debug.get("selected_ocr_block", {}),
        "spotify_matching_skipped": True,
        "youtube_result": {
            "success": youtube_result.get("success", False),
            "selected_stage": youtube_result.get("selected_stage"),
            "text_stage": youtube_result.get("text_stage"),
            "youtube_title": youtube_title,
            "ocr_used": True,
            "acr_used": False,
            "is_single_artist": youtube_result.get("is_single_artist", False),
            "inferred_artist": youtube_result.get("inferred_artist", ""),
            "single_artist_detection": youtube_result.get("single_artist_detection", {}),
            "vision_text": vision_text,
            "ocr_text": vision_debug.get("raw_ocr_text", vision_text),
            "ocr_blocks": vision_debug.get("ocr_blocks", []),
            "selected_ocr_block": vision_debug.get("selected_ocr_block", {}),
            "signals": youtube_result.get("signals", {}),
            "metrics": youtube_result.get("metrics", {}),
            "debug": {"vision": vision_debug},
        },
        "debug": {
            "selected_stage": youtube_result.get("selected_stage"),
            "vision": vision_debug,
        },
        "timings": {
            "analysis_elapsed_ms": analysis_elapsed_ms,
            "spotify_elapsed_ms": 0,
            "total_elapsed_ms": total_elapsed_ms,
        },
        "analysis_elapsed_ms": analysis_elapsed_ms,
        "spotify_elapsed_ms": 0,
        "total_elapsed_ms": total_elapsed_ms,
    }


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
    total_started_at = time.perf_counter()

    if not youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")

    access_token = _require_spotify_access_token(request, session_service)
    try:
        youtube_result, songs, analysis_elapsed_ms = _run_youtube_analysis(youtube_url, mode)
    except HTTPException:
        raise
    youtube_title = (youtube_result.get("youtube_title") or "").strip()
    final_playlist_name = _playlist_name(title_mode, user_playlist_name, youtube_title)

    try:
        spotify_started_at = time.perf_counter()
        spotify_result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=final_playlist_name,
            songs=songs,
            playlist_description=f"Created from YouTube: {youtube_title or youtube_url}",
            public=True,
            high_confidence_only=True,
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

        response_payload = {
            "success": True,
            "message": spotify_result.get("message", ""),
            "youtube_url": youtube_url,
            "youtube_title": youtube_title,
            "title_mode": title_mode,
            "mode": mode,
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
        return _json_safe(response_payload)

    except SpotifyServiceError as exc:
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
    mode = _normalize_mode(payload.get("mode") or payload.get("extraction_mode") or "text")
    skip_spotify_matching = bool(payload.get("skip_spotify_matching", False))
    total_started_at = time.perf_counter()

    if not youtube_url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")

    if bool(payload.get("demo", False)):
        demo_payload = _load_demo_cache().get(youtube_url)
        if demo_payload:
            return _json_safe(demo_payload)

    print("[playlist/analyze-youtube] request payload =", payload)
    print("[playlist/analyze-youtube] analysis start mode =", mode)
    access_token = _require_spotify_access_token(request, session_service)
    analysis_started_at = time.perf_counter()
    youtube_result = run_youtube_pipeline(youtube_url, mode=mode)
    analysis_elapsed_ms = int((time.perf_counter() - analysis_started_at) * 1000)
    songs = _fuzzy_dedup_songs(_dedupe_pipeline_songs(youtube_result.get("songs", [])))
    for song in songs:
        song["source_mode"] = mode
    print(
        "[playlist/analyze-youtube] analysis end selected_stage=",
        youtube_result.get("selected_stage"),
        "songs=",
        len(songs),
    )

    if not songs:
        total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
        no_songs_message = _make_no_songs_message(mode, youtube_result)
        response_payload = _build_analysis_response(
            youtube_url=youtube_url,
            youtube_result=youtube_result,
            songs=songs,
            results=[],
            title_mode=title_mode,
            user_playlist_name=user_playlist_name,
            mode=mode,
            analysis_elapsed_ms=analysis_elapsed_ms,
            spotify_elapsed_ms=0,
            total_elapsed_ms=total_elapsed_ms,
            message=no_songs_message,
        )
        print("[playlist/analyze-youtube] return partial response keys =", list(response_payload.keys()))
        print("[playlist/analyze-youtube] before json_safe (no songs)")
        safe_payload = _json_safe(response_payload)
        print("[playlist/analyze-youtube] after json_safe (no songs)")
        return safe_payload

    if skip_spotify_matching:
        total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
        ocr_warning = str(youtube_result.get("warning") or "")
        ocr_message = ocr_warning or "OCR/텍스트 곡 추출을 완료했습니다."
        response_payload = _build_ocr_preview_response(
            youtube_url=youtube_url,
            youtube_result=youtube_result,
            songs=songs,
            title_mode=title_mode,
            user_playlist_name=user_playlist_name,
            mode=mode,
            analysis_elapsed_ms=analysis_elapsed_ms,
            total_elapsed_ms=total_elapsed_ms,
            message=ocr_message,
        )
        print(
            "[playlist/analyze-youtube] skip spotify matching, returning OCR/text response songs =",
            len(songs),
        )
        print("[playlist/analyze-youtube] skip response ready keys =", list(response_payload.keys()))
        print("[playlist/analyze-youtube] before json_safe (skip matching)")
        safe_payload = _json_safe(response_payload)
        print("[playlist/analyze-youtube] after json_safe (skip matching)")
        return safe_payload

    try:
        print("[playlist/analyze-youtube] spotify matching start")
        spotify_started_at = time.perf_counter()
        results = analyze_spotify_candidates(
            access_token=access_token,
            songs=songs,
            market="KR",
            source_mode=mode,
        )
        spotify_elapsed_ms = int((time.perf_counter() - spotify_started_at) * 1000)
        print("[playlist/analyze-youtube] spotify matching end results =", len(results))
    except SpotifyServiceError as exc:
        total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
        partial_results = [_source_only_candidate(song) for song in songs]
        enrich_results_album_images(access_token, partial_results, market="KR")
        response_payload = _build_analysis_response(
            youtube_url=youtube_url,
            youtube_result=youtube_result,
            songs=songs,
            results=partial_results,
            title_mode=title_mode,
            user_playlist_name=user_playlist_name,
            mode=mode,
            analysis_elapsed_ms=analysis_elapsed_ms,
            spotify_elapsed_ms=0,
            total_elapsed_ms=total_elapsed_ms,
            message="OCR/텍스트 곡 추출은 완료됐지만 Spotify 후보 검색에 실패했습니다.",
            spotify_error=str(exc),
        )
        print("[playlist/analyze-youtube] spotify matching failed, returning partial response =", str(exc))
        print("[playlist/analyze-youtube] before json_safe (spotify error)")
        safe_payload = _json_safe(response_payload)
        print("[playlist/analyze-youtube] after json_safe (spotify error)")
        return safe_payload

    total_elapsed_ms = int((time.perf_counter() - total_started_at) * 1000)
    response_payload = _build_analysis_response(
        youtube_url=youtube_url,
        youtube_result=youtube_result,
        songs=songs,
        results=results,
        title_mode=title_mode,
        user_playlist_name=user_playlist_name,
        mode=mode,
        analysis_elapsed_ms=analysis_elapsed_ms,
        spotify_elapsed_ms=spotify_elapsed_ms,
        total_elapsed_ms=total_elapsed_ms,
        message="Spotify 매칭 후보를 찾았습니다.",
    )
    print(
        "[playlist/analyze-youtube] response summary =",
        {
            "mode": mode,
            "selected_stage": response_payload.get("selected_stage"),
            "songs": len(response_payload.get("songs", [])),
            "results": len(response_payload.get("results", [])),
            "matched_tracks": len(response_payload.get("matched_tracks", [])),
            "unmatched_tracks": len(response_payload.get("unmatched_tracks", [])),
        },
    )
    print("[playlist/analyze-youtube] return response keys =", list(response_payload.keys()))
    print("[playlist/analyze-youtube] before json_safe (full response)")
    safe_payload = _json_safe(response_payload)
    print("[playlist/analyze-youtube] after json_safe (full response)")
    return safe_payload


@router.post("/create-selected")
def create_playlist_from_selected_tracks(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    youtube_url = (payload.get("youtube_url") or "").strip()
    youtube_title = (payload.get("youtube_title") or "").strip()
    title_mode = (payload.get("title_mode") or "youtube").strip().lower()
    user_playlist_name = (payload.get("playlist_name") or "").strip()
    playlist_name = _playlist_name(title_mode, user_playlist_name, youtube_title)
    description = (payload.get("description") or "").strip()
    thumbnail_url = (payload.get("thumbnail_url") or "").strip()
    track_uris = payload.get("track_uris") or []

    if not isinstance(track_uris, list):
        raise HTTPException(status_code=400, detail="track_uris must be a list")

    unique_track_uris = []
    seen = set()
    for uri in track_uris:
        normalized = _normalize_spotify_track_uri(uri)
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

        # 프론트가 썸네일을 표시할 수 있도록 실제로 사용할 URL 계산
        effective_thumbnail_url = thumbnail_url
        if not effective_thumbnail_url and youtube_url:
            try:
                vid = extract_video_id(youtube_url)
                effective_thumbnail_url = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
            except YouTubeThumbnailError:
                pl_id = extract_playlist_id(youtube_url)
                if pl_id:
                    effective_thumbnail_url = get_playlist_thumbnail_url(pl_id) or ""
        result["thumbnail_url"] = effective_thumbnail_url

        if result.get("playlist_id"):
            try:
                if thumbnail_url:
                    image_base64 = get_thumbnail_base64_from_image_url(thumbnail_url)
                elif youtube_url:
                    image_base64 = get_thumbnail_base64_from_youtube_url(youtube_url)
                else:
                    image_base64 = None
                if image_base64:
                    upload_playlist_cover_image(
                        access_token=access_token,
                        playlist_id=result["playlist_id"],
                        image_base64=image_base64,
                    )
                    result["cover_upload_status"] = "success"
            except (YouTubeThumbnailError, SpotifyCoverUploadError, Exception) as exc:
                result["cover_upload_status"] = "failed"
                result["cover_upload_error"] = str(exc)
        return result
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc


@router.post("/create")
def create_playlist_from_selected_tracks_alias(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    return create_playlist_from_selected_tracks(payload, request, session_service)


@router.post("/match-songs")
def match_songs_with_spotify(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    songs_raw = payload.get("songs") or []

    songs = _fuzzy_dedup_songs(_dedupe_pipeline_songs(songs_raw))
    if not songs:
        raise HTTPException(status_code=400, detail="유효한 곡 정보가 없습니다.")

    access_token = _require_spotify_access_token(request, session_service)

    started_at = time.perf_counter()

    try:
        results = analyze_spotify_candidates(
            access_token=access_token,
            songs=songs,
            market="KR",
            source_mode="manual",
        )
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    candidate_count = sum(1 for item in results if item.get("matched") and item.get("spotify_uri"))
    needs_review_count = sum(1 for item in results if item.get("confidence_label") in {"mid", "low"})
    failed_count = sum(1 for item in results if item.get("confidence_label") == "failed")
    matched_tracks = [item for item in results if item.get("matched") and item.get("spotify_uri")]
    unmatched_tracks = [item for item in results if not (item.get("matched") and item.get("spotify_uri"))]

    return _json_safe({
        "success": True,
        "songs": songs,
        "results": results,
        "matched_tracks": matched_tracks,
        "unmatched_tracks": unmatched_tracks,
        "extracted_count": len(songs),
        "spotify_candidate_count": candidate_count,
        "candidate_count": candidate_count,
        "needs_review_count": needs_review_count,
        "failed_count": failed_count,
        "spotify_elapsed_ms": elapsed_ms,
    })
