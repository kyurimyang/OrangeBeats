import re
import unicodedata
from collections import Counter

from app.clients.youtube_client import collect_text_sources
from app.acr.acr_pipeline import extract_songs_with_acr
from app.services.fallback_extraction import extract_songs_with_ocr
from app.services.text_analysis import analyze_comments_prioritized, analyze_description

_AI_PLAYLIST_KEYWORDS = [
    # 한국어
    "ai 음악", "ai음악", "인공지능 음악", "인공지능음악",
    "ai로 만든", "ai가 만든", "ai 커버", "ai커버",
    "ai 생성", "ai생성", "ai 제작", "ai제작",
    "ai 노래", "ai노래",
    # 영어
    "ai generated", "ai-generated", "ai music", "ai cover", "ai song",
    "suno", "udio", "artificial intelligence music",
]

_SINGLE_ARTIST_PATTERNS = [
    re.compile(
        r"(?P<artist>[A-Za-z0-9&.'’ _\-\uAC00-\uD7A3]{2,40})\s*"
        r"(?:\uB178\uB798\s*\uBAA8\uC74C|\uD50C\uB808\uC774\uB9AC\uC2A4\uD2B8|playlist|songs?|best|hits|\uC804\uACE1|\uBAA8\uC74C)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\uB178\uB798\s*\uBAA8\uC74C|\uD50C\uB808\uC774\uB9AC\uC2A4\uD2B8|playlist|songs?|best|hits|\uC804\uACE1|\uBAA8\uC74C)"
        r"\s*(?:of|by|for|:|-)?\s*(?P<artist>[A-Za-z0-9&.'’ _\-\uAC00-\uD7A3]{2,40})",
        re.IGNORECASE,
    ),
]

_ARTIST_CONTEXT_STOPWORDS = {
    "playlist",
    "songs",
    "song",
    "best",
    "hits",
    "music",
    "kpop",
    "k-pop",
    "ost",
    "live",
    "mix",
    "favorite",
    "favorites",
    "my",
    "new",
    "top",
    "study",
    "chill",
    "\uB178\uB798",
    "\uBAA8\uC74C",
    "\uD50C\uB808\uC774\uB9AC\uC2A4\uD2B8",
    "\uC804\uACE1",
}


def _clean_artist_context(value: str) -> str:
    value = re.sub(r"[\[\](){}]", " ", value or "")
    value = re.sub(r"(?i)\b(?:official|lyrics?|mv|music video|audio)\b", " ", value)
    value = re.sub(r"[#|/:~]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_")
    return value.strip()


def _is_plausible_artist_context(value: str) -> bool:
    normalized = _clean_artist_context(value)
    if len(normalized) < 2 or len(normalized) > 40:
        return False
    lowered = normalized.lower()
    if lowered in _ARTIST_CONTEXT_STOPWORDS:
        return False
    tokens = [token for token in re.split(r"\s+", lowered) if token]
    if tokens and all(token in _ARTIST_CONTEXT_STOPWORDS for token in tokens):
        return False
    return bool(re.search(r"[A-Za-z0-9\uAC00-\uD7A3]", normalized))


def _normalize_unicode_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"[\[\](){}]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _detect_single_artist_from_text(title: str, description: str) -> dict:
    candidates = []
    for text in [_normalize_unicode_text(title), _normalize_unicode_text(description)]:
        for pattern in _SINGLE_ARTIST_PATTERNS:
            for match in pattern.finditer(text):
                artist = _clean_artist_context(match.group("artist"))
                if _is_plausible_artist_context(artist):
                    candidates.append(artist)

    if not candidates:
        return {"is_single_artist": False, "inferred_artist": "", "source": ""}

    counter = Counter(candidate.lower() for candidate in candidates)
    winner_key, _ = counter.most_common(1)[0]
    inferred_artist = next(candidate for candidate in candidates if candidate.lower() == winner_key)
    return {"is_single_artist": True, "inferred_artist": inferred_artist, "source": "title_description"}


def _detect_single_artist_from_songs(songs: list[dict]) -> dict:
    artists = [
        _clean_artist_context(str(song.get("artist") or ""))
        for song in songs
        if isinstance(song, dict) and _is_plausible_artist_context(str(song.get("artist") or ""))
    ]
    if len(artists) < 2:
        return {"is_single_artist": False, "inferred_artist": "", "source": ""}

    counter = Counter(artist.lower() for artist in artists)
    winner_key, winner_count = counter.most_common(1)[0]
    ratio = winner_count / max(len(artists), 1)
    if ratio < 0.7:
        return {"is_single_artist": False, "inferred_artist": "", "source": ""}

    inferred_artist = next(artist for artist in artists if artist.lower() == winner_key)
    return {
        "is_single_artist": True,
        "inferred_artist": inferred_artist,
        "source": "extracted_songs",
        "artist_ratio": round(ratio, 3),
        "artist_sample_count": len(artists),
    }


def _apply_single_artist_context(result: dict, detection: dict) -> dict:
    inferred_artist = (detection or {}).get("inferred_artist", "")
    if not inferred_artist:
        return result

    updated_songs = []
    changed = False
    for song in result.get("songs", []):
        if not isinstance(song, dict):
            continue
        item = dict(song)
        artist = (item.get("artist") or "").strip()
        title = (item.get("title") or "").strip()
        artist_missing = not artist and title
        artist_same_as_title = bool(artist and title and artist.lower() == title.lower())
        if artist_missing or artist_same_as_title:
            item["artist"] = inferred_artist
            item["artist_exists"] = True
            item["is_complete"] = True
            item["completeness_score"] = max(float(item.get("completeness_score") or 0.0), 1.0)
            item["artist_inferred"] = True
            item["inferred_artist_source"] = (detection or {}).get("source") or "single_artist_context"
            changed = True
        updated_songs.append(item)

    if changed:
        result = {**result, "songs": updated_songs}
        metrics = dict(result.get("metrics") or {})
        total_count = len(updated_songs)
        complete_count = sum(1 for song in updated_songs if song.get("is_complete"))
        avg_completeness = (
            sum(song.get("completeness_score", 0.0) for song in updated_songs) / total_count
            if total_count else 0.0
        )
        result["metrics"] = {
            **metrics,
            "song_count": total_count,
            "complete_song_count": complete_count,
            "avg_completeness": round(avg_completeness, 3),
        }

    return result


def _merge_single_artist_detection(primary: dict, songs_result: dict) -> dict:
    if primary.get("is_single_artist"):
        return primary
    if songs_result.get("is_single_artist"):
        return songs_result
    return {"is_single_artist": False, "inferred_artist": "", "source": ""}


def _single_artist_payload(detection: dict) -> dict:
    return {
        "is_single_artist": bool((detection or {}).get("is_single_artist")),
        "inferred_artist": (detection or {}).get("inferred_artist", ""),
        "single_artist_detection": detection or {"is_single_artist": False, "inferred_artist": "", "source": ""},
    }


def _detect_ai_playlist(title: str, description: str, comments: list) -> bool:
    texts = [title.lower(), description.lower()]
    for c in comments[:10]:
        text = (c.get("text", "") if isinstance(c, dict) else str(c)).lower()
        texts.append(text)
    combined = " ".join(texts)
    return any(kw in combined for kw in _AI_PLAYLIST_KEYWORDS)


def _fallback_recommendation(description_result: dict, comments_result: dict) -> dict:
    signals = {
        "description": description_result.get("signals", {}),
        "comments": comments_result.get("signals", {}),
    }
    failure_reasons = [
        reason
        for reason in [
            description_result.get("failure_reason"),
            comments_result.get("failure_reason"),
        ]
        if reason
    ]
    visible_tracklist_possible = any(
        (item or {}).get("timestamp_count", 0) >= 2
        or (item or {}).get("pattern_count", 0) >= 2
        or bool((item or {}).get("has_tracklist_structure"))
        for item in signals.values()
    )
    text_is_noisy_or_empty = all(
        reason in {"too_short", "no_timestamps", "no_pattern", "noisy_comments", "too_few_songs_without_pattern"}
        for reason in failure_reasons
    ) if failure_reasons else True

    if visible_tracklist_possible:
        return {
            "recommended_stage": "ocr",
            "reason": "visible_tracklist_possible",
            "message": "description/comments에서 패턴 신호는 보이지만 곡 추출이 부족합니다. 화면에 트랙리스트가 있을 가능성이 있어 OCR을 먼저 추천합니다.",
            "acr_limit_notice": "",
        }

    if text_is_noisy_or_empty:
        return {
            "recommended_stage": "acr",
            "reason": "no_text_or_visible_tracklist_signal",
            "message": "description/comments에서 곡 정보 신호가 약합니다. 화면에도 트랙리스트 단서가 없으면 ACR 오디오 인식을 추천합니다.",
            "acr_limit_notice": "ACR은 서비스 DB에 등록되지 않은 음원, 짧은 구간, 전환부에서는 인식하지 못할 수 있습니다.",
        }

    return {
        "recommended_stage": "ocr",
        "reason": "low_completeness_or_pattern_gap",
        "message": "텍스트 곡 정보가 불완전합니다. 화면 트랙리스트가 있다면 OCR을 추천합니다.",
        "acr_limit_notice": "",
    }


def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_text = source_data.get("description", "")
    comments = source_data.get("comment_items") or source_data.get("comments", [])
    youtube_title = source_data.get("youtube_title", "")
    title_artist_detection = _detect_single_artist_from_text(youtube_title, description_text)
    title_inferred_artist = title_artist_detection.get("inferred_artist", "")

    if _detect_ai_playlist(youtube_title, description_text, comments):
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": youtube_title,
            "selected_stage": "text",
            "text_stage": "none",
            "success": False,
            "failure_reason": "ai_playlist",
            "is_ai_playlist": True,
            "fallback_recommendation": {},
            "songs": [],
            "ocr_used": False,
            "acr_used": False,
            "signals": {},
            "metrics": {},
            "debug": {},
            **_single_artist_payload(title_artist_detection),
        }

    description_result = analyze_description(description_text, inferred_artist=title_inferred_artist)
    if description_result["success"]:
        artist_detection = _merge_single_artist_detection(
            title_artist_detection,
            _detect_single_artist_from_songs(description_result.get("songs", [])),
        )
        description_result = _apply_single_artist_context(description_result, artist_detection)
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "description",
            "success": True,
            "songs": description_result["songs"],
            "ocr_used": False,
            "acr_used": False,
            "signals": description_result["signals"],
            "metrics": description_result["metrics"],
            "failure_reason": "",
            "is_partial_but_valid": description_result.get("is_partial_but_valid", False),
            "validity_reason": description_result.get("validity_reason", ""),
            "debug": {
                "description": description_result,
            },
            **_single_artist_payload(artist_detection),
        }

    comments_result = analyze_comments_prioritized(comments, inferred_artist=title_inferred_artist)
    if comments_result["success"]:
        artist_detection = _merge_single_artist_detection(
            title_artist_detection,
            _detect_single_artist_from_songs(comments_result.get("songs", [])),
        )
        comments_result = _apply_single_artist_context(comments_result, artist_detection)
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
            "ocr_used": False,
            "acr_used": False,
            "signals": comments_result["signals"],
            "metrics": comments_result["metrics"],
            "failure_reason": "",
            "is_partial_but_valid": comments_result.get("is_partial_but_valid", False),
            "validity_reason": comments_result.get("validity_reason", ""),
            "source_priority_used": comments_result.get("source_priority_used", "expanded_comments"),
            "debug": {
                "description": description_result,
                "comments": comments_result,
            },
            **_single_artist_payload(artist_detection),
        }

    fallback_recommendation = _fallback_recommendation(description_result, comments_result)
    return {
        "input_url": source_data["input_url"],
        "video_id": source_data["video_id"],
        "youtube_title": source_data.get("youtube_title", ""),
        "selected_stage": "text",
        "text_stage": "none",
        "success": False,
        "failure_reason": comments_result.get("failure_reason") or description_result.get("failure_reason") or "no_pattern",
        "fallback_recommendation": fallback_recommendation,
        "source_priority_used": comments_result.get("source_priority_used", "expanded_comments"),
        "songs": [],
        "ocr_used": False,
        "acr_used": False,
        "signals": {
            "description": description_result["signals"],
            "comments": comments_result["signals"],
        },
        "metrics": {
            "description": description_result["metrics"],
            "comments": comments_result["metrics"],
        },
        "debug": {
            "description": description_result,
            "comments": comments_result,
        },
        **_single_artist_payload(title_artist_detection),
    }


def run_youtube_pipeline(url: str, mode: str = "text") -> dict:
    mode = (mode or "text").strip().lower()

    if mode == "ocr":
        result = extract_songs_with_ocr(url)
        title_artist_detection = _detect_single_artist_from_text(result.get("youtube_title", ""), "")
        artist_detection = _merge_single_artist_detection(
            title_artist_detection,
            _detect_single_artist_from_songs(result.get("songs", [])),
        )
        result = _apply_single_artist_context(result, artist_detection)
        result.update(_single_artist_payload(artist_detection))
        result["input_url"] = url
        result["mode"] = "ocr"
        return result

    if mode == "acr":
        result = extract_songs_with_acr(url)
        artist_detection = _detect_single_artist_from_songs(result.get("songs", []))
        result = _apply_single_artist_context(result, artist_detection)
        result.update(_single_artist_payload(artist_detection))
        result["input_url"] = url
        result["mode"] = "acr"
        return result

    text_result = run_youtube_text_pipeline(url)
    text_result["mode"] = "text"
    text_result["selected_stage"] = "text"
    text_result["ocr_used"] = False
    text_result["acr_used"] = False
    return text_result
