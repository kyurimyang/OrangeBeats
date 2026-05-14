import re
import unicodedata
from collections import Counter

from app.clients.youtube_client import collect_text_sources, get_video_music_section
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

_KR_PLAYLIST_KW = r"노래\s*모음|플레이리스트|전곡|음악\s*모음|모음"
_EN_PLAYLIST_KW = r"playlist|songs?|best|hits|collection|discography"
_ALL_PLAYLIST_KW = rf"(?:{_KR_PLAYLIST_KW}|{_EN_PLAYLIST_KW})"

_SINGLE_ARTIST_PATTERNS = [
    # 아티스트 앞: "wave to earth 노래모음", "IU playlist"
    # {2,40}? (non-greedy) → 그리디 매칭이 한국어 키워드를 artist에 먹지 않도록
    re.compile(
        r"(?P<artist>[A-Za-z0-9&.’’ _\-가-힣]{2,40}?)\s*"
        + _ALL_PLAYLIST_KW,
        re.IGNORECASE,
    ),
    # 아티스트 뒤: "playlist by wave to earth", "모음 - IU"
    re.compile(
        _ALL_PLAYLIST_KW
        + r"\s*(?:of|by|for|:|-)?\s*(?P<artist>[A-Za-z0-9&.’’ _\-가-힣]{2,40})",
        re.IGNORECASE,
    ),
]

# 한국어 동사/형용사 종결어미 — 이것으로 끝나는 문자열은 아티스트명이 아닐 가능성이 높음
# 예: "아 누구 고르지", "같이 가자", "너무 좋아"
_KR_SENTENCE_ENDING = re.compile(
    r"[가-힣](?:지|요|죠|다|가|야|해|고|자|네|군|나|까|랑|서|면|며|나요|지요|거든|잖아|니까|는데|ㄴ데)$"
)

# 설명란 해시태그에서 아티스트 후보 추출용
_HASHTAG_PATTERN = re.compile(r"#([A-Za-z가-힣][A-Za-z0-9가-힣_]{1,30})")

# 해시태그 stopword — 장르·무드·플랫폼 태그
_HASHTAG_STOPWORDS = {
    "kpop", "krnb", "rnb", "hiphop", "힙합", "팝", "pop", "indie", "인디",
    "playlist", "플레이리스트", "감성", "lofi", "chillout", "chill",
    "music", "뮤직", "노래", "가사", "lyrics", "cover", "커버",
    "shorts", "유튜브", "youtube", "spotify", "멜론", "지니",
    "추천", "신곡", "발라드", "ballad", "ost",
}

_ARTIST_CONTEXT_STOPWORDS = {
    "playlist",
    "songs",
    "song",
    "best",
    "hits",
    "music",
    "collection",
    "discography",
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
    "\uC74C\uC545",
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
    if _KR_SENTENCE_ENDING.search(normalized):
        return False
    return bool(re.search(r"[A-Za-z0-9\uAC00-\uD7A3]", normalized))


def _extract_hashtag_artists(description: str) -> list[str]:
    """\uC124\uBA85\uB780 \uD574\uC2DC\uD0DC\uADF8\uC5D0\uC11C \uC544\uD2F0\uC2A4\uD2B8 \uD6C4\uBCF4 \uCD94\uCD9C. stopword\u00B7\uBB38\uC7A5\uD615 \uD544\uD130 \uC801\uC6A9."""
    candidates = []
    for match in _HASHTAG_PATTERN.finditer(description or ""):
        tag = match.group(1).replace("_", " ").strip()
        if tag.lower() in _HASHTAG_STOPWORDS:
            continue
        if _is_plausible_artist_context(tag):
            candidates.append(tag)
    return candidates


def _normalize_unicode_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"[\[\](){}]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _detect_single_artist_from_text(title: str, description: str) -> dict:
    # 설명란 해시태그가 있으면 title-pattern보다 우선 사용
    hashtag_candidates = _extract_hashtag_artists(description)
    if hashtag_candidates:
        counter = Counter(c.lower() for c in hashtag_candidates)
        winner_key, _ = counter.most_common(1)[0]
        inferred_artist = next(c for c in hashtag_candidates if c.lower() == winner_key)
        return {"is_single_artist": True, "inferred_artist": inferred_artist, "source": "description_hashtag"}

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


def _music_section_confirmed_artists(songs: list[dict]) -> set[str]:
    return {
        _clean_artist_context(str(song.get("artist") or "")).casefold()
        for song in songs
        if (
            isinstance(song, dict)
            and song.get("music_section_confirmed")
            and _clean_artist_context(str(song.get("artist") or ""))
        )
    }


def _override_single_artist_detection_with_music_section(detection: dict, songs: list[dict]) -> dict:
    if not (detection or {}).get("is_single_artist"):
        return detection
    if (detection or {}).get("source") != "description_hashtag":
        return detection

    music_section_artists = _music_section_confirmed_artists(songs)
    if len(music_section_artists) < 2:
        return detection

    return {
        "is_single_artist": False,
        "inferred_artist": "",
        "source": "music_section_multi_artist_override",
        "previous_detection": detection,
        "music_section_artist_count": len(music_section_artists),
    }


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


def _normalize_title_for_match(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^\w\s가-힣]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _titles_match(text_title: str, section_title: str) -> bool:
    """정규화된 제목 매칭. 음악 섹션이 '곡명 (Sung by ...)' 형태일 때도 허용."""
    t = _normalize_title_for_match(text_title)
    s = _normalize_title_for_match(section_title)
    return t == s or s.startswith(t + " ") or t.startswith(s + " ")


def _enrich_songs_with_music_section(
    songs: list[dict], video_id: str
) -> tuple[list[dict], list[dict]]:
    """텍스트 추출 곡과 YouTube 음악 섹션을 교차 검증.

    Returns:
        enriched: 신뢰도·아티스트가 보강된 원본 곡 목록
        extras:   음악 섹션에만 있는 곡 (미확인 후보)
    """
    music_section = get_video_music_section(video_id)
    if not music_section:
        return songs, []

    matched_section_idx: set[int] = set()
    enriched: list[dict] = []

    for song in songs:
        match_idx, match = next(
            ((i, ms) for i, ms in enumerate(music_section) if _titles_match(song.get("title", ""), ms["title"])),
            (None, None),
        )

        song = dict(song)

        if match is not None:
            matched_section_idx.add(match_idx)
            # 아티스트 누락/추론 상태면 음악 섹션 값으로 교체
            if not song.get("artist") or song.get("artist_inferred"):
                song["artist"] = match["artist"]
                song["artist_exists"] = True
                song["is_complete"] = True
                song["completeness_score"] = max(float(song.get("completeness_score") or 0.0), 1.0)
                song["artist_inferred"] = False
                song["inferred_artist_source"] = "youtube_music_section"
            if match.get("album"):
                song["album"] = match["album"]
            song["music_section_confirmed"] = True
            song["confidence"] = "high"
        else:
            song["music_section_confirmed"] = False
            song["confidence"] = "low" if song.get("artist_inferred") else "medium"
            if not song.get("artist_inferred"):
                song["source_tag"] = "description_only"

        enriched.append(song)

    # 포지션 기반 보강: 제목 매칭 실패한 곡 ↔ 미매칭 음악 섹션 항목을 순서로 연결
    # "메아리"(챕터 0번) ↔ "Love Me Now - NCT 127"(음악 섹션 0번) 케이스 처리
    unmatched_section = [
        (i, ms) for i, ms in enumerate(music_section) if i not in matched_section_idx
    ]
    unmatched_song_indices = [
        idx for idx, s in enumerate(enriched) if not s.get("music_section_confirmed")
    ]
    for rank, song_idx in enumerate(unmatched_song_indices):
        if rank >= len(unmatched_section):
            break
        sec_idx, sec = unmatched_section[rank]
        song = dict(enriched[song_idx])
        if not song.get("artist") or song.get("artist_inferred"):
            song["artist"] = sec["artist"]
            song["artist_exists"] = True
            song["is_complete"] = True
            song["completeness_score"] = max(float(song.get("completeness_score") or 0.0), 1.0)
            song["artist_inferred"] = False
            song["inferred_artist_source"] = "youtube_music_section_positional"
        if sec.get("album"):
            song["album"] = sec["album"]
        song["music_section_confirmed"] = "positional"
        song["music_section_title_hint"] = sec["title"]
        song["confidence"] = "medium"
        enriched[song_idx] = song
        matched_section_idx.add(sec_idx)

    # 멀티 아티스트 확정 시 미확인 곡의 잘못된 추론 아티스트 제거
    # music section이 2종류 이상 아티스트를 확인했으면 해시태그 등으로 추론된 단일 아티스트는 신뢰 불가
    confirmed_artists = {
        s["artist"].strip()
        for s in enriched
        if s.get("music_section_confirmed") and s.get("artist")
    }
    if len(confirmed_artists) >= 2:
        for s in enriched:
            if s.get("artist_inferred") and not s.get("music_section_confirmed"):
                s["artist"] = ""
                s["artist_exists"] = False
                s["is_complete"] = bool(s.get("title"))
                s["artist_inferred"] = False
                s["inferred_artist_source"] = ""
                s["confidence"] = "low"

    extras = [
        {
            "title": ms["title"],
            "artist": ms["artist"],
            "album": ms.get("album", ""),
            "source": "music_section_only",
        }
        for i, ms in enumerate(music_section)
        if i not in matched_section_idx
    ]

    return enriched, extras


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
        description_result["songs"], music_extras = _enrich_songs_with_music_section(
            description_result["songs"], source_data["video_id"]
        )
        artist_detection = _override_single_artist_detection_with_music_section(
            artist_detection,
            description_result["songs"],
        )
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "description",
            "success": True,
            "songs": description_result["songs"],
            "music_section_candidates": music_extras,
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
        comments_result["songs"], music_extras = _enrich_songs_with_music_section(
            comments_result["songs"], source_data["video_id"]
        )
        artist_detection = _override_single_artist_detection_with_music_section(
            artist_detection,
            comments_result["songs"],
        )
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
            "music_section_candidates": music_extras,
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
