import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from app.services.spotify_api import add_tracks_to_playlist, create_playlist, get_tracks_by_ids
from app.services.spotify_common import _is_suspicious_song, build_match_cache_key
from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_matching import (
    explain_match_reason,
    get_match_debug,
    pick_best_track_match,
    resolve_spotify_artist_id,
)

LOW_CONF_MIN_SCORE = 0.60
HIGH_CONF_AUTO_CREATE_SCORE = 0.85
_MAX_MATCH_WORKERS = 4
ALLOWED_LOW_CONF_REASONS = {
    "probable_match",
    "review_needed",
    "low_confidence",
    "title_matched_artist_alias_candidate",
    "artist_matched_title_mismatch",
    "top_candidate_artist_romanization_title_mismatch",
    "artist_matched_title_alias_candidate",
    "version_candidate",
    "partial_match_needs_review",
}


def _single_artist_name_from_songs(songs: List[Dict[str, Any]]) -> str:
    music_section_artists = {
        str(song.get("artist") or "").strip().casefold()
        for song in songs
        if (
            isinstance(song, dict)
            and song.get("music_section_confirmed")
            and str(song.get("artist") or "").strip()
        )
    }
    if len(music_section_artists) >= 2:
        return ""

    names = {
        str(song.get("artist") or "").strip()
        for song in songs
        if (
            isinstance(song, dict)
            and song.get("artist_inferred")
            and str(song.get("artist_inference_confidence") or "").strip().lower() == "high"
            and not song.get("music_section_confirmed")
            and str(song.get("artist") or "").strip()
        )
    }
    if len(names) == 1:
        return next(iter(names))

    artist_names = [
        str(song.get("artist") or "").strip()
        for song in songs
        if isinstance(song, dict) and str(song.get("artist") or "").strip()
    ]
    if len(artist_names) < 2:
        return ""

    counts: Dict[str, int] = {}
    display_names: Dict[str, str] = {}
    for name in artist_names:
        key = name.lower()
        counts[key] = counts.get(key, 0) + 1
        display_names.setdefault(key, name)

    key, count = max(counts.items(), key=lambda item: item[1])
    if count / max(len(artist_names), 1) < 0.7:
        return ""
    return display_names[key]


def _resolve_single_artist_context(
    access_token: str,
    songs: List[Dict[str, Any]],
    market: str = "KR",
) -> Dict[str, Any]:
    artist_name = _single_artist_name_from_songs(songs)
    if not artist_name:
        return {}
    try:
        resolved = resolve_spotify_artist_id(access_token, artist_name, market=market)
    except SpotifyServiceError as exc:
        print(
            "[spotify] single_artist_context: artist resolve failed, continuing without filter:",
            str(exc),
        )
        return {}
    if not resolved.get("id"):
        return {}
    return {
        "spotify_artist_id": resolved.get("id", ""),
        "spotify_artist_name": resolved.get("name", artist_name),
        "spotify_artist_resolve_score": resolved.get("score", 0.0),
    }


def _single_artist_filter_decision(song: Dict[str, Any], single_artist_context: Dict[str, Any]) -> Dict[str, Any]:
    if song.get("music_section_confirmed"):
        return {
            "applied": False,
            "reason": "music_section_confirmed",
            "context": {},
        }
    if not single_artist_context:
        return {
            "applied": False,
            "reason": "no_single_artist_context",
            "context": {},
        }
    if not song.get("artist_inferred"):
        return {
            "applied": False,
            "reason": "artist_not_inferred",
            "context": {},
        }
    inferred_source = str(song.get("inferred_artist_source") or "").strip()
    if inferred_source and inferred_source in {"description_hashtag", "title_description", "single_artist_context"}:
        return {
            "applied": False,
            "reason": f"weak_inferred_artist_source:{inferred_source or 'unknown'}",
            "context": {},
        }
    inference_confidence = str(song.get("artist_inference_confidence") or "").strip().lower()
    if inference_confidence != "high":
        return {
            "applied": False,
            "reason": f"soft_single_artist_context:{inferred_source or 'unknown'}",
            "context": {},
        }

    return {
        "applied": True,
        "reason": "artist_inferred_without_music_section",
        "context": single_artist_context,
    }


def _match_worker_count(song_count: int) -> int:
    if song_count >= 40:
        return 2
    if song_count >= 20:
        return 3
    return _MAX_MATCH_WORKERS


def _confidence_label(match_status: str, score: float, has_uri: bool) -> str:
    if not has_uri or match_status == "invalid_candidate":
        return "failed"
    if match_status in {"review_needed", "low_confidence"} and score >= LOW_CONF_MIN_SCORE:
        return "mid"
    if match_status == "review_needed":
        return "low"
    if match_status == "matched" or score >= 0.82:
        return "high"
    if match_status == "probable_match" or score >= 0.70:
        return "mid"
    return "low"


def _spotify_track_uri_from_value(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith("spotify:track:"):
        return s
    if "open.spotify.com" in s and "/track/" in s:
        m = re.search(r"/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]{22})", s)
        if m:
            return f"spotify:track:{m.group(1)}"
    tid = _track_id_from_result_row({"spotify_track_id": s, "spotify_uri": s})
    if tid:
        return f"spotify:track:{tid}"
    return s if s.startswith("spotify:") else ""


def _track_id_from_result_row(row: Dict[str, Any]) -> str | None:
    tid = row.get("spotify_track_id")
    if tid:
        s = str(tid).strip()
        if s:
            return s
    uri = str(row.get("spotify_uri") or "").strip()
    if uri.startswith("spotify:track:"):
        tail = uri.split(":")[-1].strip()
        return tail or None
    # 웹 공유 링크만 있는 경우(또는 intl-xx 경로) — 배치 트랙 조회로 커버를 채우려면 ID 추출 필요
    if "open.spotify.com" in uri and "/track/" in uri:
        m = re.search(r"/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)", uri)
        if m:
            return m.group(1)
    return None


def _join_artists_field(raw: Any) -> str:
    """매칭 객체의 artists가 str 목록이든 Spotify 원본(dict) 목록이든 공통으로 문자열로 합친다."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if not isinstance(raw, list):
        return ""
    parts: List[str] = []
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
        elif isinstance(item, dict):
            s = str(item.get("name") or "").strip()
        else:
            continue
        if s:
            parts.append(s)
    return ", ".join(parts)


def _album_cover_url_from_track(track: Dict[str, Any]) -> str | None:
    images = (track.get("album") or {}).get("images") or []
    for img in images:
        if not isinstance(img, dict):
            continue
        u = img.get("url")
        if isinstance(u, str) and u.strip().startswith(("http://", "https://")):
            return u.strip()
    return None


def _stamp_ui_display_lines(results: List[Dict[str, Any]]) -> None:
    """결과 리스트 UI(곡명 위·가수 아래)용 — spotify_title/artist 최종값을 ui_*에 복사한다."""
    for row in results:
        row["ui_track_line"] = (row.get("spotify_title") or "").strip()
        row["ui_artist_line"] = (row.get("spotify_artist") or "").strip()


def enrich_results_album_images(access_token: str, results: List[Dict[str, Any]], market: str = "KR") -> None:
    """트랙 ID가 있으면 /tracks 배치 조회로 커버·공식 곡명·아티스트를 채운다(기존 커버가 있어도 메타는 동기화)."""
    id_to_indices: Dict[str, List[int]] = {}
    for idx, row in enumerate(results):
        tid = _track_id_from_result_row(row)
        if not tid:
            continue
        id_to_indices.setdefault(tid, []).append(idx)

    if not id_to_indices:
        _stamp_ui_display_lines(results)
        return

    unique_ids = list(id_to_indices.keys())
    try:
        fetched = get_tracks_by_ids(access_token, unique_ids, market=market)
    except SpotifyServiceError as exc:
        print("[enrich_results_album_images] get_tracks_by_ids failed:", str(exc))
    else:
        for tid, track in zip(unique_ids, fetched):
            if not track:
                continue
            url = _album_cover_url_from_track(track)
            display_name = (track.get("name") or "").strip()
            artists_raw = track.get("artists") or []
            display_artist = ", ".join(
                (a.get("name") or "").strip()
                for a in artists_raw
                if isinstance(a, dict) and (a.get("name") or "").strip()
            )
            for i in id_to_indices.get(tid, []):
                row = results[i]
                # 검색 단계에서 앨범 이미지가 비어 있어도 /tracks 응답으로 항상 동기화
                if url:
                    row["album_image"] = url
                if display_name:
                    row["spotify_title"] = display_name
                if display_artist:
                    row["spotify_artist"] = display_artist
                track_uri = track.get("uri")
                if isinstance(track_uri, str) and track_uri.strip():
                    row["spotify_uri"] = track_uri.strip()
    finally:
        _stamp_ui_display_lines(results)


def _selection_recommended(confidence_label: str, *, source_mode: str = "") -> bool:
    if source_mode == "ocr":
        return confidence_label == "high"
    return confidence_label in {"high", "mid"}


def _is_successful_match(match: Dict[str, Any]) -> bool:
    if not match.get("uri"):
        return False
    match_status = str(match.get("match_status") or "")
    return match_status == "matched"


def _sum_values(value: Any) -> float:
    if isinstance(value, dict):
        return round(sum(float(item or 0.0) for item in value.values()), 4)
    return 0.0


def _confidence_detail(match: Dict[str, Any] | None, confidence_label: str = "failed") -> Dict[str, Any]:
    if not match:
        return {
            "pattern": "failed",
            "match_status": "unmatched",
            "candidate_decision": "rejected",
        }

    detail = match.get("score_detail", {}) or {}
    evidence_detail = detail.get("evidence_confidence")
    if isinstance(evidence_detail, dict):
        nested_evidence = evidence_detail.get("evidence_detail", {}) if isinstance(evidence_detail.get("evidence_detail"), dict) else {}
        return {
            **evidence_detail,
            "match_status": str(match.get("match_status") or ""),
            "final_score": float(detail.get("final_score", match.get("score", 0.0)) or 0.0),
            "title_score": float(detail.get("title_variant_score", detail.get("title_score", nested_evidence.get("title_similarity", 0.0))) or 0.0),
            "artist_score": float(detail.get("artist_variant_score", detail.get("artist_score", nested_evidence.get("artist_similarity", 0.0))) or 0.0),
            "artist_alias_matched": bool(detail.get("artist_alias_matched") or nested_evidence.get("artist_alias_matched")),
            "version_penalty_applied": bool(detail.get("version_penalty_applied") or evidence_detail.get("version_penalty_applied")),
            "api_rank": detail.get("api_rank"),
            "query_used": detail.get("query_used", ""),
            "query_type": detail.get("query_type", ""),
            "query_reliability": detail.get("query_reliability", ""),
            "search_engine_signal_applied": bool(detail.get("search_engine_signal")),
            "rank_bonus_applied": bool(evidence_detail.get("query_evidence", {}).get("applied")),
            "notation_difference_detected": bool(detail.get("notation_difference_detected")),
            "notation_difference_reason": detail.get("notation_difference_reason", ""),
            "matched_evidence": detail.get("matched_evidence", []),
            "missing_evidence": detail.get("missing_evidence", []),
            "blocked_reason": detail.get("blocked_reason") or detail.get("search_engine_signal_blocked_reason", ""),
            "candidate_decision": evidence_detail.get("decision"),
            "raw_detail": detail,
        }

    match_status = str(match.get("match_status") or detail.get("match_status") or "")
    pattern = detail.get("pattern") or match_status or ",".join(detail.get("pattern_tags", [])[:1]) or "unknown"
    decision = detail.get("candidate_decision")
    if not decision:
        if confidence_label == "failed":
            decision = "rejected"
        elif confidence_label == "low":
            decision = "warning"
        else:
            decision = "selectable"

    return {
        "pattern": pattern,
        "match_status": match_status,
        "title_score": float(detail.get("title_variant_score", detail.get("title_score", 0.0)) or 0.0),
        "artist_score": float(detail.get("artist_variant_score", detail.get("artist_score", 0.0)) or 0.0),
        "token_score": float(detail.get("input_candidate_token_overlap", detail.get("token_score", 0.0)) or 0.0),
        "alias_bonus": _sum_values({k: v for k, v in (detail.get("bonuses") or {}).items() if "alias" in k or "variant" in k}),
        "exact_bonus": _sum_values({k: v for k, v in (detail.get("bonuses") or {}).items() if "exact" in k}),
        "penalty": _sum_values(detail.get("penalties") or {}),
        "final_score": float(detail.get("final_score", match.get("score", 0.0)) or 0.0),
        "api_rank": detail.get("api_rank"),
        "query_used": detail.get("query_used", ""),
        "query_type": detail.get("query_type", ""),
        "query_reliability": detail.get("query_reliability", ""),
        "search_engine_signal_applied": bool(detail.get("search_engine_signal")),
        "rank_bonus_applied": bool(detail.get("rank_bonus_applied", detail.get("search_engine_signal"))),
        "notation_difference_detected": bool(detail.get("notation_difference_detected")),
        "notation_difference_reason": detail.get("notation_difference_reason", ""),
        "matched_evidence": detail.get("matched_evidence", []),
        "missing_evidence": detail.get("missing_evidence", []),
        "blocked_reason": detail.get("blocked_reason") or detail.get("search_engine_signal_blocked_reason", ""),
        "candidate_decision": decision,
        "raw_detail": detail,
    }


def _result_from_match(
    song: Dict[str, Any],
    match: Dict[str, Any] | None,
    *,
    include_debug: bool = False,
    source_mode: str = "",
) -> Dict[str, Any]:
    input_artist = (song.get("artist") or "").strip()
    input_title = (song.get("title") or "").strip()
    debug = get_match_debug(input_title, input_artist)

    if not match:
        reason = debug.get("unmatched_reason") or "no reliable Spotify match"
        reason_text = explain_match_reason(str(reason).split("(", 1)[0]) or reason
        result: Dict[str, Any] = {
            "input_artist": input_artist,
            "input_title": input_title,
            "matched": False,
            "spotify_track_id": None,
            "spotify_uri": None,
            "spotify_title": None,
            "spotify_artist": None,
            "album_image": None,
            "confidence": 0,
            "score": 0,
            "status": "unmatched",
            "confidence_label": "failed",
            "reason": [reason_text],
            "reason_text": reason_text,
            "confidence_detail": _confidence_detail(None),
            "selected": False,
            "match_status": "unmatched",
            "top_candidates": debug.get("top_candidates", []),
        }
        if include_debug:
            result["match_debug"] = debug
        return result

    score = float(match.get("score") or 0.0)
    match_status = str(match.get("match_status") or "matched")
    spotify_uri = match.get("uri")
    confidence_label = _confidence_label(match_status, score, bool(spotify_uri))
    is_ocr_mode = source_mode == "ocr" or str(song.get("source_mode") or "") == "ocr"
    auto_selectable = match_status == "matched" and (not is_ocr_mode or confidence_label == "high")
    reason_key = match.get("low_confidence_reason")
    if not reason_key and not isinstance(match.get("reason"), list):
        reason_key = match.get("reason")
    reason = (
        match.get("user_message")
        or explain_match_reason(reason_key or match_status)
        or reason_key
        or "Spotify candidate found"
    )
    reason_array = match.get("reason") if isinstance(match.get("reason"), list) else []
    if not reason_array:
        reason_array = [str(reason)]
    status = str(match.get("status") or ("low_confidence" if confidence_label == "low" else match_status))

    album_image = match.get("album_image")
    if isinstance(album_image, str) and album_image.strip().startswith(("http://", "https://")):
        album_image = album_image.strip()
    else:
        album_image = None
        for cand in match.get("top_candidates") or []:
            if not isinstance(cand, dict):
                continue
            img = cand.get("album_image")
            if isinstance(img, str) and img.strip().startswith(("http://", "https://")):
                album_image = img.strip()
                break

    return {
        "input_artist": input_artist,
        "input_title": input_title,
        "matched": bool(spotify_uri) and match_status == "matched",
        "spotify_track_id": match.get("id"),
        "spotify_uri": spotify_uri,
        "spotify_title": match.get("name"),
        "spotify_artist": _join_artists_field(match.get("artists")),
        "album_image": album_image,
        "confidence": round(score, 4),
        "score": round(score, 4),
        "final_score": round(float(match.get("final_score", score) or 0.0), 4),
        "status": status,
        "applied_pattern": match.get("applied_pattern") or (match.get("score_detail") or {}).get("applied_pattern", ""),
        "evidence_detail": (match.get("score_detail") or {}).get("evidence_detail", {}),
        "translated_title_candidate": bool(match.get("translated_title_candidate") or (match.get("score_detail") or {}).get("translated_title_candidate")),
        "official_metadata_candidate": bool(match.get("official_metadata_candidate") or (match.get("score_detail") or {}).get("official_metadata_candidate")),
        "search_engine_signal_reason": (match.get("score_detail") or {}).get("search_engine_signal_reason", ""),
        "confidence_label": confidence_label,
        "reason": reason_array,
        "reason_text": str(reason),
        "confidence_detail": _confidence_detail(match, confidence_label),
        "selected": bool(spotify_uri) and auto_selectable and _selection_recommended(confidence_label, source_mode="ocr" if is_ocr_mode else ""),
        "match_status": match_status,
        "top_candidates": match.get("top_candidates", []),
        "match_debug": debug,
    }


def analyze_spotify_candidates(
    access_token: str,
    songs: List[Dict[str, Any]],
    market: str = "KR",
    source_mode: str = "",
) -> List[Dict[str, Any]]:
    request_match_cache: Dict[tuple[str, str], Any] = {}
    cache_lock = threading.Lock()
    single_artist_context = _resolve_single_artist_context(access_token, songs, market=market)

    # Phase 1: 입력 준비 (I/O 없음, 순차 처리)
    prepared: List[Dict[str, Any]] = []
    for song in songs:
        title = (song.get("title") or "").strip()
        artist = (song.get("artist") or "").strip()
        if not title:
            prepared.append({"skip": "no_title", "song": song, "title": title, "artist": artist})
            continue
        if _is_suspicious_song(song):
            prepared.append({"skip": "suspicious", "song": song, "title": title, "artist": artist})
            continue
        filter_decision = _single_artist_filter_decision(song, single_artist_context)
        song_single_artist_context = filter_decision["context"]
        # artist_inferred + music_section 미확인 → single artist filter로만 제한하고 title-only 검색
        search_artist = None if filter_decision["applied"] else (artist or None)
        song_meta = {
            "raw": song.get("raw", ""),
            "left": song.get("left", ""),
            "right": song.get("right", ""),
            "swap_applied": song.get("swap_applied", False),
            "global_direction": song.get("global_direction", "per_line"),
            "chosen_case": song.get("chosen_case", "original"),
            "score": song.get("score", 0.0),
            "reason": song.get("reason", ""),
            "swap_guard_applied": song.get("swap_guard_applied", False),
            "swap_guard_reason": song.get("swap_guard_reason", ""),
            "source_mode": source_mode or song.get("source_mode", ""),
            "acr_spotify_track_id": song.get("acr_spotify_track_id", ""),
            "title_metadata_hints": song.get("title_metadata_hints", []),
            "title_feature_artists": song.get("title_feature_artists", []),
            "title_producer_artists": song.get("title_producer_artists", []),
            "raw_line": song.get("raw_line", ""),
            "evidence_type": song.get("evidence_type", ""),
            "ocr_evidence": song.get("ocr_evidence", {}),
            "acr_evidence": song.get("acr_evidence", {}),
            **song_single_artist_context,
        }
        cache_key = build_match_cache_key(
            title,
            f"{search_artist or ''}|artist_id:{song_single_artist_context.get('spotify_artist_id', '')}",
        )
        prepared.append({
            "skip": None,
            "song": song,
            "title": title,
            "artist": artist,
            "search_artist": search_artist,
            "song_meta": song_meta,
            "filter_decision": filter_decision,
            "song_single_artist_context": song_single_artist_context,
            "cache_key": cache_key,
        })

    # Phase 2: 병렬 Spotify 검색 (I/O)
    def _fetch_match(item: Dict[str, Any]) -> Any:
        if item["skip"]:
            return None
        key = item["cache_key"]
        with cache_lock:
            if key in request_match_cache:
                return request_match_cache[key]
        match = pick_best_track_match(
            access_token=access_token,
            title=item["title"],
            artist=item["search_artist"],
            market=market,
            song_meta=item["song_meta"],
        )
        with cache_lock:
            request_match_cache[key] = match
        return match

    with ThreadPoolExecutor(max_workers=_match_worker_count(len(prepared))) as executor:
        matches = list(executor.map(_fetch_match, prepared))

    # Phase 3: 결과 조립 (순서 보존, 순차 처리)
    results: List[Dict[str, Any]] = []
    for item, match in zip(prepared, matches):
        song = item["song"]
        if item["skip"] == "no_title":
            results.append(_result_from_match(song, None))
            continue
        if item["skip"] == "suspicious":
            results.append({
                "input_artist": item["artist"],
                "input_title": item["title"],
                "matched": False,
                "spotify_track_id": None,
                "spotify_uri": None,
                "spotify_title": None,
                "spotify_artist": None,
                "album_image": None,
                "confidence": 0,
                "confidence_label": "failed",
                "reason": "artist/title information is not reliable enough",
                "selected": False,
                "match_status": "unmatched",
                "top_candidates": [],
            })
            continue
        title = item["title"]
        search_artist = item["search_artist"]
        filter_decision = item["filter_decision"]
        song_single_artist_context = item["song_single_artist_context"]
        result = _result_from_match(song, match, source_mode=source_mode or str(song.get("source_mode") or ""))
        search_debug = get_match_debug(title, search_artist or "")
        result["single_artist_filter_applied"] = bool(filter_decision["applied"])
        result["single_artist_filter_reason"] = str(filter_decision["reason"])
        result["single_artist_mode"] = bool(filter_decision["applied"])
        if filter_decision["applied"]:
            result["spotify_artist_id_filter"] = song_single_artist_context.get("spotify_artist_id", "")
            result["spotify_artist_name_filter"] = song_single_artist_context.get("spotify_artist_name", "")
        debug = {
            **search_debug,
            **dict(result.get("match_debug") or {}),
        }
        debug["single_artist_filter_applied"] = bool(filter_decision["applied"])
        debug["single_artist_filter_reason"] = str(filter_decision["reason"])
        debug["spotify_artist_id_filter"] = song_single_artist_context.get("spotify_artist_id", "")
        result["match_debug"] = debug
        results.append(result)

    enrich_results_album_images(access_token, results, market=market)

    # 같은 Spotify track ID로 매칭된 중복 결과 제거 (한국어/영어 교차 중복 등)
    best_by_track: Dict[str, int] = {}
    for i, result in enumerate(results):
        tid = result.get("spotify_track_id")
        if not tid:
            continue
        if tid not in best_by_track or result.get("confidence", 0) > results[best_by_track[tid]].get("confidence", 0):
            best_by_track[tid] = i
    results = [
        r for i, r in enumerate(results)
        if not r.get("spotify_track_id") or best_by_track.get(r["spotify_track_id"]) == i
    ]

    return results


def create_playlist_from_track_uris(
    access_token: str,
    playlist_name: str,
    track_uris: List[str],
    playlist_description: str = "",
    public: bool = True,
) -> Dict[str, Any]:
    unique_uris: List[str] = []
    seen = set()
    for uri in track_uris:
        normalized = _spotify_track_uri_from_value(uri)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_uris.append(normalized)

    if not unique_uris:
        raise SpotifyServiceError("선택된 곡이 없습니다.")

    playlist = create_playlist(
        access_token=access_token,
        name=playlist_name or "YouTube Playlist",
        description=playlist_description,
        public=public,
    )
    add_tracks_to_playlist(
        access_token=access_token,
        playlist_id=playlist["id"],
        track_uris=unique_uris,
    )

    return {
        "success": True,
        "playlist_id": playlist["id"],
        "playlist_url": playlist["external_urls"]["spotify"],
        "added_count": len(unique_uris),
        "deduped_count": len(track_uris) - len(unique_uris),
    }


def _low_confidence_allowed_reason(match: Dict[str, Any]) -> str:
    for key in ("reason", "match_status", "low_confidence_reason"):
        value = str(match.get(key) or "").strip()
        if value in ALLOWED_LOW_CONF_REASONS:
            return value
    return ""


def _low_confidence_skip_reason(match: Dict[str, Any]) -> str:
    if not match.get("uri"):
        return "missing_uri"
    if float(match.get("score") or 0.0) < LOW_CONF_MIN_SCORE:
        return "score_too_low"
    if not _low_confidence_allowed_reason(match):
        return "reason_not_allowed"
    return ""


def _matching_rate_percent(matched_count: int, low_confidence_count: int, unmatched_count: int) -> float:
    total = matched_count + low_confidence_count + unmatched_count
    if total <= 0:
        return 0.0
    return round(((matched_count + low_confidence_count) / total) * 100, 1)


def _candidate_summary(candidate: Dict[str, Any], fallback_case: str) -> Dict[str, Any]:
    return {
        'name': candidate.get('name', ''),
        'artists': candidate.get('artists', []),
        'score': candidate.get('score', 0.0),
        'popularity': candidate.get('popularity', 0),
        'orientation': candidate.get('orientation', 'artist_title'),
        'chosen_case': candidate.get('chosen_case', fallback_case),
        'match_status': candidate.get('match_status', ''),
        'low_confidence_reason': candidate.get('low_confidence_reason', ''),
        'unmatched_reason': candidate.get('unmatched_reason', ''),
        'user_message': candidate.get('user_message', ''),
        'score_detail': candidate.get('score_detail', {}),
    }


def create_playlist_from_songs(
    access_token: str,
    playlist_name: str,
    songs: List[Dict[str, str]],
    playlist_description: str = '',
    public: bool = True,
    high_confidence_only: bool = False,
) -> Dict[str, Any]:
    if not songs:
        raise SpotifyServiceError('생성할 곡 목록이 없습니다.')

    request_match_cache: Dict[tuple[str, str], Any] = {}
    cache_lock = threading.Lock()
    single_artist_context = _resolve_single_artist_context(access_token, songs, market='KR')

    # Phase 1: 입력 준비 (I/O 없음, 순차 처리)
    prepared: List[Dict[str, Any]] = []
    for song in songs:
        title = (song.get('title') or '').strip()
        input_artist = (song.get('artist') or '').strip()
        if not title:
            prepared.append({'skip': 'no_title', 'song': song, 'title': title, 'artist': input_artist})
            continue
        if _is_suspicious_song(song):
            prepared.append({'skip': 'suspicious', 'song': song, 'title': title, 'artist': input_artist})
            continue
        filter_decision = _single_artist_filter_decision(song, single_artist_context)
        song_single_artist_context = filter_decision["context"]
        search_artist = None if filter_decision["applied"] else (input_artist or None)
        song_meta = {
            'raw': song.get('raw', ''),
            'left': song.get('left', ''),
            'right': song.get('right', ''),
            'swap_applied': song.get('swap_applied', False),
            'global_direction': song.get('global_direction', 'per_line'),
            'chosen_case': song.get('chosen_case', 'original'),
            'score': song.get('score', 0.0),
            'reason': song.get('reason', ''),
            'swap_guard_applied': song.get('swap_guard_applied', False),
            'swap_guard_reason': song.get('swap_guard_reason', ''),
            'acr_spotify_track_id': song.get('acr_spotify_track_id', ''),
            'title_metadata_hints': song.get('title_metadata_hints', []),
            'title_feature_artists': song.get('title_feature_artists', []),
            'title_producer_artists': song.get('title_producer_artists', []),
            'raw_line': song.get('raw_line', ''),
            'evidence_type': song.get('evidence_type', ''),
            'ocr_evidence': song.get('ocr_evidence', {}),
            'acr_evidence': song.get('acr_evidence', {}),
            **song_single_artist_context,
        }
        cache_key = build_match_cache_key(
            title,
            f"{search_artist or ''}|artist_id:{song_single_artist_context.get('spotify_artist_id', '')}",
        )
        prepared.append({
            'skip': None,
            'song': song,
            'title': title,
            'artist': input_artist,
            'search_artist': search_artist,
            'song_meta': song_meta,
            'filter_decision': filter_decision,
            'song_single_artist_context': song_single_artist_context,
            'cache_key': cache_key,
        })

    # Phase 2: 병렬 Spotify 검색 (I/O)
    def _fetch_match_create(item: Dict[str, Any]) -> Any:
        if item['skip']:
            return None
        key = item['cache_key']
        with cache_lock:
            if key in request_match_cache:
                return request_match_cache[key]
        match = pick_best_track_match(
            access_token=access_token,
            title=item['title'],
            artist=item['search_artist'],
            market='KR',
            song_meta=item['song_meta'],
        )
        with cache_lock:
            request_match_cache[key] = match
        return match

    with ThreadPoolExecutor(max_workers=_match_worker_count(len(prepared))) as executor:
        matches = list(executor.map(_fetch_match_create, prepared))

    # Phase 3: 결과 조립 (순서 보존, 순차 처리)
    matched_uris: List[str] = []
    playlist_uris: List[str] = []
    matched_debug: List[Dict[str, Any]] = []
    low_confidence: List[Dict[str, Any]] = []
    added_low_confidence: List[Dict[str, Any]] = []
    skipped_low_confidence: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_uris = set()

    for item, match in zip(prepared, matches):
        song = item['song']
        title = item['title']
        input_artist = item['artist']
        if item['skip'] == 'no_title':
            unmatched.append({'song': song, 'reason': 'title 없음'})
            continue
        if item['skip'] == 'suspicious':
            unmatched.append({'song': song, 'reason': 'artist/title 동일 또는 정보 부족'})
            continue
        filter_decision = item['filter_decision']
        song_single_artist_context = item['song_single_artist_context']
        song_meta = item['song_meta']
        search_artist = item['search_artist']

        if not match:
            debug = get_match_debug(title, search_artist or '')
            unmatched_reason = debug.get('unmatched_reason') or 'no_search_result'
            unmatched.append({
                'song': song,
                'reason': unmatched_reason,
                'unmatched_reason': unmatched_reason,
                'match_status': 'unmatched',
                'score_detail': {},
                'user_message': explain_match_reason(str(unmatched_reason).split('(', 1)[0]),
                'search_title': debug.get('search_title', title),
                'search_artist': debug.get('search_artist', search_artist or ''),
                'chosen_case': debug.get('selected_case', song_meta['chosen_case']),
                'single_artist_filter_applied': bool(filter_decision['applied']),
                'single_artist_filter_reason': str(filter_decision['reason']),
                'spotify_artist_id_filter': song_single_artist_context.get('spotify_artist_id', ''),
                'top_candidates': debug.get('top_candidates', []),
                'case_results': debug.get('case_results', []),
            })
            continue

        match_status = match.get('match_status', 'matched')
        if (
            high_confidence_only
            and match_status == 'matched'
            and float(match.get('score') or 0.0) < HIGH_CONF_AUTO_CREATE_SCORE
        ):
            low_confidence.append({
                'input': {
                    'artist': input_artist,
                    'title': title,
                },
                'matched_name': match.get('name', ''),
                'matched_title': match.get('name', ''),
                'matched_artists': match.get('artists', []),
                'score': match.get('score', 0.0),
                'match_status': 'review_needed',
                'reason': 'high_confidence_only_gate',
                'low_confidence_reason': 'high_confidence_only_gate',
                'user_message': '자동 생성에서는 high-confidence 곡만 추가합니다. 이 후보는 사용자 확인이 필요합니다.',
                'score_detail': match.get('score_detail', {}),
                'search_title': match.get('search_title', ''),
                'search_artist': match.get('search_artist', ''),
                'chosen_case': match.get('chosen_case', song_meta['chosen_case']),
                'swap_applied': song_meta['swap_applied'],
                'global_direction': song_meta['global_direction'],
                'parse_reason': song_meta['reason'],
                'parse_score': song_meta['score'],
                'single_artist_filter_applied': bool(filter_decision['applied']),
                'single_artist_filter_reason': str(filter_decision['reason']),
                'spotify_artist_id_filter': song_single_artist_context.get('spotify_artist_id', ''),
                'top_candidates': [
                    _candidate_summary(candidate, match.get('chosen_case', song_meta['chosen_case']))
                    for candidate in match.get('top_candidates', [])
                ],
            })
            skipped_low_confidence.append({
                'input': {
                    'artist': input_artist,
                    'title': title,
                },
                'matched_name': match.get('name', ''),
                'score': match.get('score', 0.0),
                'skip_reason': 'high_confidence_only_gate',
                'user_message': '자동 생성에서는 high-confidence 곡만 추가합니다.',
            })
            continue
        if not _is_successful_match(match):
            low_conf_reason = match.get('low_confidence_reason', '') or match.get('reason', '')
            low_confidence_item = {
                'input': {
                    'artist': input_artist,
                    'title': title,
                },
                'matched_name': match.get('name', ''),
                'matched_title': match.get('name', ''),
                'matched_artists': match.get('artists', []),
                'score': match.get('score', 0.0),
                'match_status': match_status,
                'reason': low_conf_reason,
                'low_confidence_reason': low_conf_reason,
                'unmatched_reason': match.get('unmatched_reason', ''),
                'user_message': match.get('user_message') or explain_match_reason(low_conf_reason),
                'score_detail': match.get('score_detail', {}),
                'search_title': match.get('search_title', ''),
                'search_artist': match.get('search_artist', ''),
                'chosen_case': match.get('chosen_case', song_meta['chosen_case']),
                'swap_applied': song_meta['swap_applied'],
                'global_direction': song_meta['global_direction'],
                'parse_reason': song_meta['reason'],
                'parse_score': song_meta['score'],
                'single_artist_filter_applied': bool(filter_decision['applied']),
                'single_artist_filter_reason': str(filter_decision['reason']),
                'spotify_artist_id_filter': song_single_artist_context.get('spotify_artist_id', ''),
                'top_candidates': [
                    _candidate_summary(candidate, match.get('chosen_case', song_meta['chosen_case']))
                    for candidate in match.get('top_candidates', [])
                ],
            }
            low_confidence.append({
                **low_confidence_item,
            })
            skip_reason = _low_confidence_skip_reason(match)
            if skip_reason:
                skipped_low_confidence.append({
                    'input': {
                        'artist': input_artist,
                        'title': title,
                    },
                    'matched_name': match.get('name', ''),
                    'score': match.get('score', 0.0),
                    'skip_reason': skip_reason,
                    'user_message': explain_match_reason(skip_reason),
                })
            else:
                uri = match.get('uri')
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    playlist_uris.append(uri)
                added_low_confidence.append({
                    'input': {
                        'artist': input_artist,
                        'title': title,
                    },
                    'matched_name': match.get('name', ''),
                    'matched_title': match.get('name', ''),
                    'matched_artists': match.get('artists', []),
                    'score': match.get('score', 0.0),
                    'reason': _low_confidence_allowed_reason(match) or low_conf_reason,
                    'low_confidence_reason': low_conf_reason,
                    'user_message': match.get('user_message') or explain_match_reason(low_conf_reason),
                    'match_status': match_status,
                    'uri': uri,
                })
            continue

        uri = match.get('uri')
        if uri and uri not in seen_uris:
            seen_uris.add(uri)
            matched_uris.append(uri)
            playlist_uris.append(uri)

        matched_debug.append({
            'input': {
                'artist': input_artist,
                'title': title,
            },
            'matched_name': match.get('name', ''),
            'matched_title': match.get('name', ''),
            'matched_artists': match.get('artists', []),
            'score': match.get('score', 0.0),
            'match_status': match_status,
            'low_confidence_reason': match.get('low_confidence_reason', ''),
            'unmatched_reason': match.get('unmatched_reason', ''),
            'user_message': match.get('user_message') or explain_match_reason(match_status),
            'score_detail': match.get('score_detail', {}),
            'chosen_case': match.get('chosen_case', song_meta['chosen_case']),
            'reason': match.get('reason', ''),
            'orientation': match.get('orientation', 'title_artist'),
            'llm_reranked': False,
            'llm_confidence': '',
            'llm_reason': '',
            'search_title': match.get('search_title', ''),
            'search_artist': match.get('search_artist', ''),
            'swap_applied': song_meta['swap_applied'],
            'global_direction': song_meta['global_direction'],
            'parse_reason': song_meta['reason'],
            'parse_score': song_meta['score'],
            'swap_guard_applied': song_meta['swap_guard_applied'],
            'swap_guard_reason': song_meta['swap_guard_reason'],
            'single_artist_filter_applied': bool(filter_decision['applied']),
            'single_artist_filter_reason': str(filter_decision['reason']),
            'spotify_artist_id_filter': song_single_artist_context.get('spotify_artist_id', ''),
            'top_candidates': [
                _candidate_summary(candidate, match.get('chosen_case', song_meta['chosen_case']))
                for candidate in match.get('top_candidates', [])
            ],
        })

    matching_rate = _matching_rate_percent(len(matched_uris), len(low_confidence), len(unmatched))

    if not playlist_uris:
        return {
            'playlist_id': None,
            'playlist_url': None,
            'playlist_created': False,
            'message': 'Spotify에 추가할 수 있는 매칭 곡이 없어 플레이리스트를 생성하지 않았습니다.',
            'matched_count': len(matched_uris),
            'unmatched_count': len(unmatched),
            'low_confidence_count': len(low_confidence),
            'matching_rate': matching_rate,
            'added_low_confidence_count': len(added_low_confidence),
            'added_low_confidence': added_low_confidence,
            'skipped_low_confidence_count': len(skipped_low_confidence),
            'skipped_low_confidence': skipped_low_confidence,
            'added_count': 0,
            'playlist_added_tracks': 0,
            'playlist_uri_count': 0,
            'single_artist_mode': bool(single_artist_context),
            'spotify_artist_context': single_artist_context,
            'matched': matched_debug,
            'low_confidence': low_confidence,
            'unmatched': unmatched,
        }

    playlist = create_playlist(
        access_token=access_token,
        name=playlist_name,
        description=playlist_description,
        public=public,
    )

    if playlist_uris:
        add_tracks_to_playlist(
            access_token=access_token,
            playlist_id=playlist['id'],
            track_uris=playlist_uris,
        )

    return {
        'playlist_id': playlist['id'],
        'playlist_url': playlist['external_urls']['spotify'],
        'playlist_created': True,
        'matched_count': len(matched_uris),
        'unmatched_count': len(unmatched),
        'low_confidence_count': len(low_confidence),
        'matching_rate': matching_rate,
        'added_low_confidence_count': len(added_low_confidence),
        'added_low_confidence': added_low_confidence,
        'skipped_low_confidence_count': len(skipped_low_confidence),
        'skipped_low_confidence': skipped_low_confidence,
        'added_count': len(playlist_uris),
        'playlist_added_tracks': len(playlist_uris),
        'playlist_uri_count': len(playlist_uris),
        'single_artist_mode': bool(single_artist_context),
        'spotify_artist_context': single_artist_context,
        'matched': matched_debug,
        'low_confidence': low_confidence,
        'unmatched': unmatched,
    }
