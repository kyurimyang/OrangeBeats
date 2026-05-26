import difflib
import re
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from app.clients.youtube_client import collect_text_sources, get_video_music_section
from app.acr.acr_pipeline import extract_songs_with_acr
from app.services.analysis_flow import merge_song_sources
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
    "playlist", "플레이리스트", "플리", "감성", "lofi", "chillout", "chill",
    "music", "뮤직", "노래", "가사", "lyrics", "cover", "커버",
    "shorts", "유튜브", "youtube", "spotify", "멜론", "지니",
    "추천", "신곡", "발라드", "ballad", "ost",
    "popsongs", "kpopsongs", "songs", "hits",
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
    # \uD55C\uAD6D\uC5B4 \uD50C\uB808\uC774\uB9AC\uC2A4\uD2B8/\uC7A5\uB974 \uB808\uC774\uBE14 \u2014 artist\uB85C \uC624\uCD94\uB860 \uBC29\uC9C0
    "\uB178\uB3D9\uC694",    # "work song" \uC18D\uC5B4 (\uBC30\uACBD\uC74C\uC545 \uBAA8\uC74C \uCC44\uB110 \uC81C\uBAA9\uC5D0 \uC790\uC8FC \uC4F0\uC784)
    "\uBE44\uD2B8",      # "beat"
    "\uB9DB\uC9D1",      # "great spot" \uC18D\uC5B4 (\uC608: "\uBE44\uD2B8 \uB9DB\uC9D1")
    "\uAC10\uC131",      # "vibe/emotion"
    "\uC778\uAE30",      # "popular"
    "\uCD5C\uC2E0",      # "latest"
    "\uC2E0\uACE1",      # "new release"
    "\uBAA8\uC74C\uC9D1",    # "compilation"
    "\uC120\uACE1",      # "track selection"
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
            if artist_same_as_title:
                item["artist"] = ""
                item["artist_exists"] = False
            item["artist_hint"] = inferred_artist
            item["artist_hint_source"] = (detection or {}).get("source") or "single_artist_context"
            item["artist_inferred"] = True
            item["inferred_artist_source"] = (detection or {}).get("source") or "single_artist_context"
            item["artist_inference_confidence"] = item.get("artist_inference_confidence") or "high"
            changed = True
        updated_songs.append(item)

    if changed:
        result = {**result, "songs": updated_songs}
        metrics = dict(result.get("metrics") or {})
        total_count = len(updated_songs)
        complete_count = sum(
            1
            for song in updated_songs
            if song.get("is_complete")
            or (song.get("title") and (song.get("artist") or song.get("artist_hint")))
        )
        avg_completeness = (
            sum(
                max(float(song.get("completeness_score") or 0.0), 0.75)
                if song.get("title") and song.get("artist_hint") and not song.get("artist")
                else float(song.get("completeness_score") or 0.0)
                for song in updated_songs
            ) / total_count
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
    # 댓글은 제외: "AI 플레이리스트 채널들 사이에서 한 줄기 빛" 같은 비교 표현이
    # AI 키워드를 포함해도 이 영상이 AI 콘텐츠임을 의미하지 않음
    combined = f"{title} {description}".lower()
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


def _combined_text_result(
    description_result: dict,
    comments_result: dict,
) -> tuple[list[dict], dict]:
    description_songs = description_result.get("songs", []) if isinstance(description_result, dict) else []
    comment_songs = comments_result.get("songs", []) if isinstance(comments_result, dict) else []
    songs = merge_song_sources(
        description_songs,
        comment_songs,
        base_source="description",
        fallback_source="comments",
    )
    successful_sources = [
        name
        for name, result in [("description", description_result), ("comments", comments_result)]
        if result.get("success")
    ]
    partial_sources = [
        name
        for name, result in [("description", description_result), ("comments", comments_result)]
        if (not result.get("success")) and result.get("songs")
    ]
    metrics = {
        "description": description_result.get("metrics", {}),
        "comments": comments_result.get("metrics", {}),
        "merged": {
            "song_count": len(songs),
            "complete_song_count": sum(1 for song in songs if song.get("artist") and song.get("title")),
        },
    }
    signals = {
        "description": description_result.get("signals", {}),
        "comments": comments_result.get("signals", {}),
    }
    return songs, {
        "successful_sources": successful_sources,
        "partial_sources": partial_sources,
        "metrics": metrics,
        "signals": signals,
    }


def _normalize_title_for_match(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^\w\s가-힣]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_base_title(title: str) -> str:
    t = re.sub(r"\s*\([^)]*\)", "", title or "").strip()
    return _normalize_title_for_match(t)


def _titles_match(text_title: str, section_title: str) -> bool:
    t = _normalize_title_for_match(text_title)
    s = _normalize_title_for_match(section_title)
    if t == s or s.startswith(t + " ") or t.startswith(s + " ") or t.endswith(" " + s) or s.endswith(" " + t):
        return True
    bt = _extract_base_title(text_title)
    bs = _extract_base_title(section_title)
    if bt and bs and len(bt) >= 2 and (bt == bs or bs.startswith(bt + " ") or bt.startswith(bs + " ")):
        return True
    has_korean_base = bool(re.search(r"[\uAC00-\uD7A3]", bt + bs))
    if has_korean_base and bt and bs and len(bt) >= 2 and len(bs) >= 2 and (bt in s or bs in t):
        return True
    return False



def _has_strong_text_evidence(song: dict) -> bool:
    confidence = str(song.get("confidence") or "").strip().lower()
    if confidence == "high":
        return True

    evidence_type = str(song.get("evidence_type") or "").strip().lower()
    if evidence_type in {"timestamp_pair", "delimiter_pair"}:
        return True

    raw_line = str(song.get("raw_line") or song.get("raw") or "").strip()
    return bool(raw_line and song.get("artist") and song.get("title") and not song.get("artist_inferred"))


def _confidence_for_unmatched_music_section(song: dict) -> str:
    existing = str(song.get("confidence") or "").strip().lower()
    if existing in {"high", "medium", "low"} and _has_strong_text_evidence(song):
        return existing
    if song.get("artist_inferred") and not _has_strong_text_evidence(song):
        return "low"
    return existing if existing in {"high", "medium", "low"} else "medium"


def _is_title_only_timestamp_song(song: dict) -> bool:
    """True when a timestamp line supplied a title but no reliable artist."""
    evidence_type = str(song.get("evidence_type") or "").strip().lower()
    if evidence_type == "title_only_timestamp":
        return True

    artist = str(song.get("artist") or "").strip()
    title = str(song.get("title") or "").strip()
    raw_line = str(song.get("raw_line") or song.get("raw") or "").strip()
    return bool(
        artist
        and title
        and artist.casefold() == title.casefold()
        and re.search(r"\b\d{1,2}:\d{2}\b", raw_line)
    )


def _should_apply_positional_music_section(
    songs: list[dict],
    music_section: list[dict],
    matched_count: int,
) -> bool:
    """Use order-only music-section hints only when the two lists clearly align."""
    if not songs or not music_section:
        return False
    if len(songs) != len(music_section):
        return False
    return matched_count > 0


def _find_best_music_section_match(
    title: str, music_section: list[dict], matched_indices: set[int]
) -> tuple[int | None, dict | None]:
    normalized = _normalize_title_for_match(title)
    if not normalized:
        return None, None

    best_score = 0.0
    best_idx: int | None = None
    best_entry: dict | None = None

    for i, ms in enumerate(music_section):
        if i in matched_indices:
            continue
        candidate = _normalize_title_for_match(ms.get("title", ""))
        if not candidate:
            continue

        if _titles_match(title, ms.get("title", "")):
            return i, ms

        if len(normalized) >= 4 and len(candidate) >= 4:
            score = difflib.SequenceMatcher(None, normalized, candidate).ratio()
            if score > best_score:
                best_score = score
                best_idx = i
                best_entry = ms

    if best_score >= 0.82 and best_idx is not None:
        return best_idx, best_entry
    return None, None


def _enrich_songs_with_music_section(
    songs: list[dict], music_section: list[dict]
) -> tuple[list[dict], list[dict]]:
    """텍스트 추출 곡과 YouTube 음악 섹션을 교차 검증.

    Returns:
        enriched: 신뢰도·아티스트가 보강된 원본 곡 목록
        extras:   음악 섹션에만 있는 곡 (미확인 후보)
    """
    if isinstance(music_section, str):
        music_section = get_video_music_section(music_section)

    if not music_section:
        return songs, []

    matched_section_idx: set[int] = set()
    enriched: list[dict] = []

    for song in songs:
        match_idx, match = _find_best_music_section_match(
            song.get("title", ""), music_section, matched_section_idx
        )

        song = dict(song)

        if match is not None:
            matched_section_idx.add(match_idx)
            # 아티스트 누락/추론 상태면 음악 섹션 값으로 교체
            if not song.get("artist") or song.get("artist_inferred") or _is_title_only_timestamp_song(song):
                if _is_title_only_timestamp_song(song):
                    song["original_text_artist"] = song.get("artist", "")
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
            song["confidence"] = _confidence_for_unmatched_music_section(song)
            if not song.get("artist_inferred"):
                song["source_tag"] = "description_only"

        enriched.append(song)

    unmatched_section = [
        (i, ms) for i, ms in enumerate(music_section) if i not in matched_section_idx
    ]
    unmatched_song_indices = [
        idx for idx, s in enumerate(enriched) if not s.get("music_section_confirmed")
    ]
    if _should_apply_positional_music_section(enriched, music_section, len(matched_section_idx)):
        for rank, song_idx in enumerate(unmatched_song_indices):
            if rank >= len(unmatched_section):
                break
            sec_idx, sec = unmatched_section[rank]
            song = dict(enriched[song_idx])
            if _is_title_only_timestamp_song(song):
                song["original_text_title"] = song.get("title", "")
                song["original_text_artist"] = song.get("artist", "")
                song["title"] = sec.get("title", "")
                song["artist"] = sec.get("artist", "")
                song["artist_exists"] = bool(song["artist"])
                song["title_exists"] = bool(song["title"])
                song["is_complete"] = bool(song["artist"] and song["title"])
                song["completeness_score"] = 1.0 if song["is_complete"] else song.get("completeness_score", 0.0)
                song["artist_inferred"] = False
                song["inferred_artist_source"] = "youtube_music_section_order"
                matched_section_idx.add(sec_idx)
            song["music_section_confirmed"] = "positional_suggestion"
            song["music_section_hint"] = {
                "title": sec.get("title", ""),
                "artist": sec.get("artist", ""),
                "album": sec.get("album", ""),
                "source": "youtube_music_section",
                "match_type": "order_only",
            }
            song["music_section_title_hint"] = sec.get("title", "")
            song["music_section_artist_hint"] = sec.get("artist", "")
            song["confidence"] = "low" if song.get("artist_inferred") else _confidence_for_unmatched_music_section(song)
            song["review_reason"] = "music_section_order_only_hint"
            enriched[song_idx] = song

    # 멀티 아티스트 확정 시 미확인 곡의 잘못된 추론 아티스트 제거
    # music section이 2종류 이상 아티스트를 확인했으면 해시태그 등으로 추론된 단일 아티스트는 신뢰 불가
    confirmed_artists = {
        s["artist"].strip()
        for s in enriched
        if s.get("music_section_confirmed") and s.get("artist")
    }
    if len(confirmed_artists) >= 2:
        for s in enriched:
            if (
                s.get("artist_inferred")
                and s.get("music_section_confirmed") is not True
                and not _has_strong_text_evidence(s)
            ):
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
            "match_type": "section_only",
        }
        for i, ms in enumerate(music_section)
        if i not in matched_section_idx
    ]

    # 설명란과 댓글의 방향 추론이 달라 artist/title이 뒤집힌 버전과 올바른 버전이
    # 함께 들어오는 경우, music section이 확인한 곡을 기준으로 swap 중복본을 제거한다.
    confirmed = [s for s in enriched if s.get("music_section_confirmed")]
    if confirmed:
        confirmed_swap_keys: set[tuple[str, str]] = {
            (
                str(s.get("title") or "").strip().casefold(),
                str(s.get("artist") or "").strip().casefold(),
            )
            for s in confirmed
            if s.get("artist") and s.get("title")
        }
        enriched = [
            s for s in enriched
            if s.get("music_section_confirmed")
            or (
                str(s.get("artist") or "").strip().casefold(),
                str(s.get("title") or "").strip().casefold(),
            )
            not in confirmed_swap_keys
        ]

    return enriched, extras


def _supplement_songs_from_candidates(
    songs: list[dict], candidates: list[dict]
) -> tuple[list[dict], list[dict]]:
    updated = list(songs)
    annotated: list[dict] = []
    for cand in candidates:
        title = (cand.get("title") or "").strip()
        artist = (cand.get("artist") or "").strip()
        if not title or not artist:
            annotated.append({**cand, "merge_decision": "excluded", "debug_reason": "missing_title_or_artist"})
            continue

        duplicate_reason = ""
        normalized_artist = _normalize_title_for_match(artist)
        for song in updated:
            if not _titles_match(str(song.get("title") or ""), title):
                continue
            song_artist = _normalize_title_for_match(str(song.get("artist") or ""))
            if normalized_artist and normalized_artist == song_artist:
                duplicate_reason = "duplicate_title_artist"
                break
            if song.get("music_section_confirmed"):
                duplicate_reason = "duplicate_music_section_title"
                break
        if duplicate_reason:
            annotated.append({**cand, "merge_decision": "excluded", "debug_reason": duplicate_reason})
            continue

        updated.append({
            "title": title,
            "artist": artist,
            "album": cand.get("album", ""),
            "source": "music_section_only",
            "source_mode": "music_section_only",
            "sources": ["music_section"],
            "raw_line": f"{artist} - {title}",
            "evidence_type": "music_section_only",
            "music_section_confirmed": "supplemental",
            "confidence": "low",
            "artist_exists": True,
            "title_exists": True,
            "is_complete": True,
            "completeness_score": 1.0,
            "artist_inferred": False,
            "review_reason": "music_section_only_candidate",
            "debug_reason": "added_from_music_section_only_missing_from_text",
        })
        annotated.append({
            **cand,
            "merge_decision": "added",
            "debug_reason": "added_from_music_section_only_missing_from_text",
        })

    return updated, annotated


def _music_section_to_songs(music_section: list[dict]) -> list[dict]:
    songs = []
    for i, ms in enumerate(music_section):
        title = (ms.get("title") or "").strip()
        artist = (ms.get("artist") or "").strip()
        if not title or not artist:
            continue
        songs.append({
            "title": title,
            "artist": artist,
            "album": ms.get("album", ""),
            "source": "music_section",
            "source_mode": "music_section",
            "raw_line": f"{artist} - {title}",
            "line_index": i,
            "evidence_type": "music_section",
            "music_section_confirmed": True,
            "confidence": "high",
            "artist_exists": True,
            "is_complete": True,
            "completeness_score": 1.0,
            "artist_inferred": False,
            "acr_evidence": {},
            "ocr_evidence": {},
            "sources": ["music_section"],
        })
    return songs


def _build_source_quality_summary(
    description_result: dict,
    comments_result: dict,
    selected_source: str,
    music_extras: list[dict],
) -> dict:
    desc_metrics = description_result.get("metrics") or {}
    comm_metrics = comments_result.get("metrics") or {}
    return {
        "selected_source": selected_source,
        "description": {
            "success": bool(description_result.get("success")),
            "song_count": desc_metrics.get("song_count", 0),
            "complete_song_count": desc_metrics.get("complete_song_count", 0),
            "avg_completeness": desc_metrics.get("avg_completeness", 0.0),
            "failure_reason": description_result.get("failure_reason", ""),
        },
        "comments": {
            "success": bool(comments_result.get("success")),
            "skipped": comments_result.get("method") == "skipped",
            "song_count": comm_metrics.get("song_count", 0),
            "complete_song_count": comm_metrics.get("complete_song_count", 0),
            "avg_completeness": comm_metrics.get("avg_completeness", 0.0),
            "failure_reason": comments_result.get("failure_reason", ""),
        },
        "music_section": {
            "role": "enrichment_only",
            "extra_candidates_count": len(music_extras),
        },
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

    # Phase 1: 설명란 파싱 + 음악 섹션 조회 병렬 실행
    with ThreadPoolExecutor(max_workers=2) as ex:
        desc_future  = ex.submit(analyze_description, description_text, inferred_artist=title_inferred_artist)
        music_future = ex.submit(get_video_music_section, source_data["video_id"])

    description_result = desc_future.result()
    prefetched_music_section = music_future.result() or []
    description_ok = bool(description_result.get("success"))

    # Phase 2: 설명란이 충분하면 댓글 스킵, 부족하면 댓글 파싱
    _skipped = {
        "stage": "comments",
        "success": False,
        "method": "skipped",
        "signals": {},
        "metrics": {},
        "songs": [],
        "source_priority_used": "none",
    }
    if description_ok:
        comments_result = {**_skipped, "failure_reason": "description_success"}
    elif comments:
        comments_result = analyze_comments_prioritized(comments, inferred_artist=title_inferred_artist)
    else:
        comments_result = {**_skipped, "failure_reason": "no_comments"}
    comments_ok = bool(comments_result.get("success"))

    # Phase 3: Priority 기반 primary source 선택 (무조건 병합 제거)
    if description_ok:
        primary_songs = description_result.get("songs", [])
        selected_source = "description"
        fallback_reason = None
    elif comments_ok:
        primary_songs = comments_result.get("songs", [])
        selected_source = "comments"
        fallback_reason = description_result.get("failure_reason") or "description_insufficient"
    else:
        # 둘 다 실패 — partial 결과만 있을 때 최후 수단으로 병합
        primary_songs = merge_song_sources(
            description_result.get("songs", []),
            comments_result.get("songs", []),
            base_source="description",
            fallback_source="comments",
        )
        selected_source = "merged_partial"
        fallback_reason = (
            comments_result.get("failure_reason")
            or description_result.get("failure_reason")
            or "both_partial"
        )

    if primary_songs:
        artist_detection = _merge_single_artist_detection(
            title_artist_detection,
            _detect_single_artist_from_songs(primary_songs),
        )
        primary_result = {
            "success": description_ok or comments_ok,
            "songs": primary_songs,
            "metrics": (
                description_result.get("metrics", {}) if description_ok
                else comments_result.get("metrics", {})
            ),
        }
        primary_result = _apply_single_artist_context(primary_result, artist_detection)

        # Phase 4: 음악 섹션으로 보강 + 텍스트 미추출 곡 자동 추가
        enriched_songs, music_extras = _enrich_songs_with_music_section(
            primary_result["songs"], prefetched_music_section
        )
        supplemented_songs, supplement_log = _supplement_songs_from_candidates(enriched_songs, music_extras)
        primary_result["songs"] = supplemented_songs

        artist_detection = _override_single_artist_detection_with_music_section(
            artist_detection,
            primary_result["songs"],
        )
        source_quality_summary = _build_source_quality_summary(
            description_result, comments_result, selected_source, music_extras
        )
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": selected_source,
            "selected_source": selected_source,
            "fallback_reason": fallback_reason,
            "source_quality_summary": source_quality_summary,
            "success": True,
            "songs": primary_result["songs"],
            "music_section_candidates": supplement_log,
            "ocr_used": False,
            "acr_used": False,
            "signals": {
                "description": description_result.get("signals", {}),
                "comments": comments_result.get("signals", {}),
            },
            "metrics": {
                "description": description_result.get("metrics", {}),
                "comments": comments_result.get("metrics", {}),
                "primary": {
                    "song_count": len(primary_result["songs"]),
                    "complete_song_count": sum(
                        1 for s in primary_result["songs"] if s.get("artist") and s.get("title")
                    ),
                },
            },
            "failure_reason": "",
            "partial_success": not (description_ok or comments_ok),
            "is_partial_but_valid": bool(
                description_result.get("is_partial_but_valid") or comments_result.get("is_partial_but_valid")
            ),
            "validity_reason": (
                description_result.get("validity_reason")
                or comments_result.get("validity_reason")
                or "priority_text_selection"
            ),
            "source_priority_used": comments_result.get("source_priority_used", "none"),
            "source_merge": {
                "description_count": len(description_result.get("songs", [])),
                "comments_count": len(comments_result.get("songs", [])),
                "primary_count": len(primary_result["songs"]),
                "selected_source": selected_source,
            },
            "debug": {
                "description": description_result,
                "comments": comments_result,
            },
            **_single_artist_payload(artist_detection),
        }

    # 텍스트에서 곡을 못 찾으면 YouTube 음악 섹션(Content ID)으로 폴백
    music_section = prefetched_music_section
    if music_section:
        section_songs = _music_section_to_songs(music_section)
        if section_songs:
            artist_detection = _merge_single_artist_detection(
                title_artist_detection,
                _detect_single_artist_from_songs(section_songs),
            )
            artist_detection = _override_single_artist_detection_with_music_section(
                artist_detection, section_songs
            )
            return {
                "input_url": source_data["input_url"],
                "video_id": source_data["video_id"],
                "youtube_title": source_data.get("youtube_title", ""),
                "selected_stage": "text",
                "text_stage": "music_section",
                "selected_source": "music_section",
                "fallback_reason": (
                    comments_result.get("failure_reason")
                    or description_result.get("failure_reason")
                    or "text_extraction_failed"
                ),
                "source_quality_summary": _build_source_quality_summary(
                    description_result, comments_result, "music_section", []
                ),
                "success": True,
                "songs": section_songs,
                "music_section_candidates": [],
                "ocr_used": False,
                "acr_used": False,
                "signals": {},
                "metrics": {
                    "primary": {
                        "song_count": len(section_songs),
                        "complete_song_count": len(section_songs),
                    }
                },
                "failure_reason": "",
                "partial_success": False,
                "is_partial_but_valid": True,
                "validity_reason": "music_section_fallback",
                "source_priority_used": "music_section",
                "source_merge": {
                    "description_count": 0,
                    "comments_count": 0,
                    "primary_count": len(section_songs),
                    "selected_source": "music_section",
                },
                "debug": {
                    "description": description_result,
                    "comments": comments_result,
                    "music_section_fallback": True,
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
        "selected_source": "none",
        "fallback_reason": comments_result.get("failure_reason") or description_result.get("failure_reason") or "no_pattern",
        "source_quality_summary": _build_source_quality_summary(
            description_result, comments_result, "none", []
        ),
        "success": False,
        "failure_reason": comments_result.get("failure_reason") or description_result.get("failure_reason") or "no_pattern",
        "fallback_recommendation": fallback_recommendation,
        "source_priority_used": comments_result.get("source_priority_used", "none"),
        "songs": [],
        "ocr_used": False,
        "acr_used": False,
        "signals": {
            "description": description_result.get("signals", {}),
            "comments": comments_result.get("signals", {}),
        },
        "metrics": {
            "description": description_result.get("metrics", {}),
            "comments": comments_result.get("metrics", {}),
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
