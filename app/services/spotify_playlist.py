from typing import Any, Dict, List

from app.services.spotify_api import add_tracks_to_playlist, create_playlist
from app.services.spotify_common import _is_suspicious_song, build_match_cache_key
from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_matching import explain_match_reason, get_match_debug, pick_best_track_match

LOW_CONF_MIN_SCORE = 0.60
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


def _selection_recommended(confidence_label: str, *, source_mode: str = "") -> bool:
    if source_mode == "ocr":
        return confidence_label == "high"
    return confidence_label in {"high", "mid"}


def _is_successful_match(match: Dict[str, Any]) -> bool:
    if not match.get("uri"):
        return False
    match_status = str(match.get("match_status") or "")
    score = float(match.get("score") or 0.0)
    if match_status in {"matched", "probable_match"}:
        return True
    return match_status in {"review_needed", "low_confidence"} and score >= LOW_CONF_MIN_SCORE


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
        return {
            **evidence_detail,
            "match_status": str(match.get("match_status") or ""),
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
    ocr_auto_selectable = not is_ocr_mode or confidence_label == "high"
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

    return {
        "input_artist": input_artist,
        "input_title": input_title,
        "matched": bool(spotify_uri) and confidence_label != "failed" and ocr_auto_selectable,
        "spotify_track_id": match.get("id"),
        "spotify_uri": spotify_uri,
        "spotify_title": match.get("name"),
        "spotify_artist": ", ".join(match.get("artists", [])),
        "album_image": match.get("album_image"),
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
        "selected": bool(spotify_uri) and _selection_recommended(confidence_label, source_mode="ocr" if is_ocr_mode else ""),
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
    results: List[Dict[str, Any]] = []
    request_match_cache: Dict[tuple[str, str], Any] = {}

    for song in songs:
        title = (song.get("title") or "").strip()
        artist = (song.get("artist") or "").strip()
        if not title:
            results.append(_result_from_match(song, None))
            continue

        if _is_suspicious_song(song):
            results.append(
                {
                    "input_artist": artist,
                    "input_title": title,
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
                }
            )
            continue

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
        }
        cache_key = build_match_cache_key(title, artist)
        if cache_key in request_match_cache:
            match = request_match_cache[cache_key]
        else:
            match = pick_best_track_match(
                access_token=access_token,
                title=title,
                artist=artist or None,
                market=market,
                song_meta=song_meta,
            )
            request_match_cache[cache_key] = match

        results.append(_result_from_match(song, match, source_mode=source_mode or str(song.get("source_mode") or "")))

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
        normalized = (uri or "").strip()
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
) -> Dict[str, Any]:
    if not songs:
        raise SpotifyServiceError('생성할 곡 목록이 없습니다.')

    matched_uris: List[str] = []
    playlist_uris: List[str] = []
    matched_debug: List[Dict[str, Any]] = []
    low_confidence: List[Dict[str, Any]] = []
    added_low_confidence: List[Dict[str, Any]] = []
    skipped_low_confidence: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_uris = set()
    request_match_cache: Dict[tuple[str, str], Any] = {}

    for song in songs:
        title = (song.get('title') or '').strip()
        artist = (song.get('artist') or '').strip() or None
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
        }

        if not title:
            unmatched.append({'song': song, 'reason': 'title 없음'})
            continue

        if _is_suspicious_song(song):
            unmatched.append({'song': song, 'reason': 'artist/title 동일 또는 정보 부족'})
            continue

        cache_key = build_match_cache_key(title, artist or '')
        if cache_key in request_match_cache:
            match = request_match_cache[cache_key]
        else:
            match = pick_best_track_match(
                access_token=access_token,
                title=title,
                artist=artist,
                market='KR',
                song_meta=song_meta,
            )
            request_match_cache[cache_key] = match

        if not match:
            debug = get_match_debug(title, artist or '')
            unmatched_reason = debug.get('unmatched_reason') or 'no_search_result'
            unmatched.append({
                'song': song,
                'reason': unmatched_reason,
                'unmatched_reason': unmatched_reason,
                'match_status': 'unmatched',
                'score_detail': {},
                'user_message': explain_match_reason(str(unmatched_reason).split('(', 1)[0]),
                'search_title': debug.get('search_title', title),
                'search_artist': debug.get('search_artist', artist or ''),
                'chosen_case': debug.get('selected_case', song_meta['chosen_case']),
                'top_candidates': debug.get('top_candidates', []),
                'case_results': debug.get('case_results', []),
            })
            continue

        match_status = match.get('match_status', 'matched')
        if not _is_successful_match(match):
            low_conf_reason = match.get('low_confidence_reason', '') or match.get('reason', '')
            low_confidence_item = {
                'input': {
                    'artist': artist or '',
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
                        'artist': artist or '',
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
                        'artist': artist or '',
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
                'artist': artist or '',
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
        'matched': matched_debug,
        'low_confidence': low_confidence,
        'unmatched': unmatched,
    }
