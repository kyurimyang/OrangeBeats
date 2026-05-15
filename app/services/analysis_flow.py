from typing import Any, Dict, List


TEXT_SUCCESS = "text_success"
PARTIAL_SUCCESS = "partial_success"
TEXT_FAILED = "text_failed"


def _clean_song_value(value: Any) -> str:
    return str(value or "").strip()


def _song_key(song: Dict[str, Any]) -> tuple[str, str]:
    return (
        _clean_song_value(song.get("artist")).casefold(),
        _clean_song_value(song.get("title")).casefold(),
    )


def _song_payload(song: Dict[str, Any], source: str) -> Dict[str, Any]:
    item = dict(song or {})
    item["artist"] = _clean_song_value(item.get("artist"))
    item["title"] = _clean_song_value(item.get("title"))
    sources = item.get("sources")
    if isinstance(sources, list):
        merged_sources = [str(value) for value in sources if value]
    else:
        merged_sources = []
    if source and source not in merged_sources:
        merged_sources.append(source)
    item["source"] = item.get("source") or source
    item["source_mode"] = item.get("source_mode") or source
    item["sources"] = merged_sources
    return item


def merge_song_sources(
    base_songs: List[Dict[str, Any]] | None,
    fallback_songs: List[Dict[str, Any]] | None,
    *,
    base_source: str = "text",
    fallback_source: str = "ocr",
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    by_key: Dict[tuple[str, str], int] = {}

    for raw_song, source in [
        *((song, base_source) for song in (base_songs or [])),
        *((song, fallback_source) for song in (fallback_songs or [])),
    ]:
        if not isinstance(raw_song, dict):
            continue
        song = _song_payload(raw_song, source)
        if not song.get("title"):
            continue
        key = _song_key(song)
        if key in by_key:
            existing = merged[by_key[key]]
            existing_sources = list(existing.get("sources") or [])
            for item_source in song.get("sources") or [source]:
                if item_source and item_source not in existing_sources:
                    existing_sources.append(item_source)
            existing["sources"] = existing_sources
            existing["source"] = existing.get("source") or song.get("source") or source
            for meta_key in [
                "timestamp",
                "raw",
                "raw_line",
                "line_index",
                "confidence",
                "evidence_type",
                "score",
                "reason",
                "reject_reason",
            ]:
                if not existing.get(meta_key) and song.get(meta_key):
                    existing[meta_key] = song.get(meta_key)
            continue
        by_key[key] = len(merged)
        merged.append(song)

    return merged


def classify_text_analysis(youtube_result: Dict[str, Any], songs: List[Dict[str, Any]]) -> Dict[str, Any]:
    songs = songs or []
    metrics = youtube_result.get("metrics") if isinstance(youtube_result.get("metrics"), dict) else {}
    total = len(songs)
    complete = sum(1 for song in songs if song.get("artist") and song.get("title"))
    avg_completeness = float(metrics.get("avg_completeness") or 0.0)
    if total and not avg_completeness:
        avg_completeness = sum(float(song.get("completeness_score") or 0.0) for song in songs) / total

    reasons: List[str] = []
    if total < 3:
        reasons.append("too_few_songs")
    if complete < 2:
        reasons.append("too_few_complete_songs")
    if total and complete / max(total, 1) < 0.7:
        reasons.append("many_incomplete_songs")
    if avg_completeness and avg_completeness < 0.6:
        reasons.append("low_completeness")
    if youtube_result.get("partial_success"):
        reasons.append("source_partial_success")
    if youtube_result.get("failure_reason"):
        reasons.append(str(youtube_result.get("failure_reason")))

    if not total or not youtube_result.get("success"):
        state = TEXT_FAILED
    elif reasons:
        state = PARTIAL_SUCCESS
    else:
        state = TEXT_SUCCESS

    needs_fallback = state in {PARTIAL_SUCCESS, TEXT_FAILED}
    return {
        "analysis_state": state,
        "needs_fallback": needs_fallback,
        "next_action": "choose_fallback" if needs_fallback else "match_candidates",
        "analysis_reasons": reasons,
        "text_quality": {
            "song_count": total,
            "complete_song_count": complete,
            "avg_completeness": round(avg_completeness, 3),
        },
    }
