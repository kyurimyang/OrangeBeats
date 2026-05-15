# 유튜브 링크 받아서 전체 파이프라인 돌리는 API 주소 파일

import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.services.analysis_flow import classify_text_analysis, merge_song_sources
from app.services.pipeline_service import run_youtube_pipeline

router = APIRouter(prefix="/youtube", tags=["YouTube"])


def _dedupe_songs(raw_songs: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    songs: List[Dict[str, Any]] = []
    seen = set()
    for raw in raw_songs or []:
        if not isinstance(raw, dict):
            continue
        artist = str(raw.get("artist") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        key = (artist.casefold(), title.casefold())
        if key in seen:
            continue
        seen.add(key)
        item = dict(raw)
        item["artist"] = artist
        item["title"] = title
        item["source"] = item.get("source") or source
        item["source_mode"] = item.get("source_mode") or source
        item["raw_line"] = item.get("raw_line", "")
        item["line_index"] = item.get("line_index", -1)
        item["evidence_type"] = item.get("evidence_type", "")
        item["acr_evidence"] = item.get("acr_evidence", {})
        item["ocr_evidence"] = item.get("ocr_evidence", {})
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        if source not in sources:
            sources = [*sources, source]
        item["sources"] = sources
        songs.append(item)
    return songs


def _response_payload(
    *,
    url: str,
    result: Dict[str, Any],
    songs: List[Dict[str, Any]],
    mode: str,
    elapsed_ms: int,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    state = classify_text_analysis(result, songs) if mode == "text" else {
        "analysis_state": "fallback_success" if songs else "fallback_failed",
        "needs_fallback": False,
        "next_action": "match_candidates" if songs else "choose_fallback",
        "analysis_reasons": [result.get("failure_reason")] if result.get("failure_reason") else [],
        "text_quality": {
            "song_count": len(songs),
            "complete_song_count": sum(1 for song in songs if song.get("artist") and song.get("title")),
            "avg_completeness": 0.0,
        },
    }
    video_id = result.get("video_id", "")
    payload = {
        "success": state["analysis_state"] in {"text_success", "partial_success", "fallback_success"},
        "youtube_url": url,
        "youtube_title": result.get("youtube_title", ""),
        "video_id": video_id,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
        "mode": mode,
        "selected_stage": result.get("selected_stage"),
        "text_stage": result.get("text_stage"),
        "ocr_used": result.get("ocr_used", False),
        "acr_used": result.get("acr_used", False),
        "songs": songs,
        "extracted_songs": songs,
        "extracted_count": len(songs),
        "spotify_matching_skipped": True,
        "youtube_result": {k: v for k, v in result.items() if k not in {"debug", "raw_texts", "ocr_blocks"}},
        "analysis_elapsed_ms": elapsed_ms,
        "spotify_elapsed_ms": 0,
        "total_elapsed_ms": elapsed_ms,
        "timings": {
            "analysis_elapsed_ms": elapsed_ms,
            "spotify_elapsed_ms": 0,
            "total_elapsed_ms": elapsed_ms,
        },
        **state,
    }
    if extra:
        payload.update(extra)
    if not payload.get("message"):
        if payload["analysis_state"] == "text_success":
            payload["message"] = "텍스트 분석이 충분합니다. Spotify 후보 검색을 진행할 수 있습니다."
        elif payload["analysis_state"] == "partial_success":
            payload["message"] = "텍스트에서 일부 곡을 찾았지만 보강 분석을 선택할 수 있습니다."
        elif payload["analysis_state"] == "text_failed":
            payload["message"] = "텍스트에서 곡 목록을 충분히 찾지 못했습니다. OCR 또는 ACR을 선택해주세요."
        elif payload["analysis_state"] == "fallback_success":
            payload["message"] = f"{mode.upper()} 분석 결과를 기존 텍스트 결과와 병합했습니다."
        else:
            payload["message"] = f"{mode.upper()} 분석에서 곡을 찾지 못했습니다."
    return payload


@router.get("/analyze")
def analyze_youtube(
    url: str = Query(...),
    mode: str = Query("text"),
):
    started_at = time.perf_counter()
    result = run_youtube_pipeline(url, mode)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    result["timings"] = {
        **result.get("timings", {}),
        "analysis_elapsed_ms": elapsed_ms,
        "total_elapsed_ms": elapsed_ms,
    }
    return result


@router.post("/analyze-text")
def analyze_youtube_text(payload: Dict[str, Any]):
    url = str(payload.get("youtube_url") or payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")

    started_at = time.perf_counter()
    result = run_youtube_pipeline(url, mode="text")
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    songs = _dedupe_songs(result.get("songs", []), "text")
    return _response_payload(url=url, result=result, songs=songs, mode="text", elapsed_ms=elapsed_ms)


@router.post("/analyze-fallback")
def analyze_youtube_fallback(payload: Dict[str, Any]):
    url = str(payload.get("youtube_url") or payload.get("url") or "").strip()
    mode = str(payload.get("mode") or payload.get("fallback_mode") or "").strip().lower()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL이 필요합니다.")
    if mode not in {"ocr", "acr"}:
        raise HTTPException(status_code=400, detail="fallback mode must be one of: ocr, acr")

    text_songs = _dedupe_songs(payload.get("text_songs") or payload.get("songs") or [], "text")
    started_at = time.perf_counter()
    result = run_youtube_pipeline(url, mode=mode)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    fallback_songs = _dedupe_songs(result.get("songs", []), mode)
    merged = merge_song_sources(text_songs, fallback_songs, base_source="text", fallback_source=mode)
    return _response_payload(
        url=url,
        result=result,
        songs=merged,
        mode=mode,
        elapsed_ms=elapsed_ms,
        extra={
            "fallback_mode": mode,
            "fallback_songs": fallback_songs,
            "text_songs": text_songs,
            "merge": {
                "text_count": len(text_songs),
                "fallback_count": len(fallback_songs),
                "merged_count": len(merged),
            },
        },
    )
