# 텍스트/JSON 파싱, 중복 제거, 성공 판정
# 설명란/LLM 결과를 곡 리스트로 정리

## 추가
# - 비음악 텍스트 제거 (URL, 안내문, 일반 문장 등)
# - artist + title 구조 검증 및 완성도 평가
# - 중복 제거 및 최종 곡 리스트 생성
# - 텍스트 기반 단계 성공 여부 판단

import json
import re
from typing import Any

from app.constants.pipeline_params import (
    MIN_PATTERN_COUNT,
    MIN_TIMESTAMP_COUNT,
    MIN_SONG_COUNT,
    MIN_COMPLETE_SONG_COUNT,
    MIN_COMPLETENESS_RATIO,
    SECTION_KEYWORDS,
    NATURAL_SENTENCE_HINTS,
    TITLE_DELIMITERS,
    NON_MUSIC_LINE_PATTERNS,
)

# regex 선언
TIME_PREFIX_REGEX = re.compile(r"^\s*(\d{1,2}:\d{2})(?::\d{2})?\s*[-|]?\s*")
MULTISPACE_REGEX = re.compile(r"\s+")
BRACKET_REGEX = re.compile(r"[\[\(\{].*?[\]\)\}]")
TIMESTAMP_LINE_REGEX = re.compile(r"^(?P<ts>\d{1,2}:\d{2})(?::\d{2})?\s+(?P<body>.+)$")
TIMESTAMP_PREFIX_ONLY_REGEX = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+")
PAIR_REGEX = re.compile(r".+\s[-–—|/]\s.+")


# LLM 응답에서 JSON만 추출 후 songs 구조로 정규화
def parse_json_from_text(text: str) -> dict:
    if not text:
        return {"songs": []}

    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"songs": []}

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict) and "songs" in parsed:
            return normalize_song_candidates(parsed)
    except:
        pass

    return {"songs": []}


# 문자열 정리 (괄호 제거 + 공백 정리)
def _clean_text(value: str) -> str:
    value = str(value)
    value = BRACKET_REGEX.sub("", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -–—:|/").strip()


# timestamp 제거 + 공백 정리
def _normalize_line(line: str) -> str:
    line = line.strip()
    line = TIME_PREFIX_REGEX.sub("", line)
    line = MULTISPACE_REGEX.sub(" ", line)
    return line.strip()


# URL, 이메일, 안내문 패턴 포함 여부
def _contains_non_music_pattern(line: str) -> bool:
    for pattern in NON_MUSIC_LINE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


# 축가, playlist 등 섹션 키워드 포함 여부
def _contains_section_keyword(line: str) -> bool:
    lower = line.lower()
    return any(k.lower() in lower for k in SECTION_KEYWORDS)


# 자연어 문장인지 판별 (곡 정보 아닌 문장 제거)
def _looks_like_natural_sentence(line: str) -> bool:
    lower = line.lower()
    has_delimiter = any(d in line for d in TITLE_DELIMITERS)

    hint = sum(1 for w in NATURAL_SENTENCE_HINTS if w in lower)
    punct = sum(lower.count(p) for p in [".", "!", "?", ","])
    words = len(lower.split())

    if hint >= 2 and not has_delimiter:
        return True
    if punct >= 2 and not has_delimiter:
        return True
    if words >= 8 and not has_delimiter:
        return True

    return False


# 곡 정보 후보 라인인지 판단
def _is_valid_music_line(line: str) -> bool:
    if not line or len(line.strip()) < 3:
        return False

    normalized = _normalize_line(line)

    if not normalized:
        return False

    if _contains_non_music_pattern(line) or _contains_non_music_pattern(normalized):
        return False

    if _contains_section_keyword(normalized):
        if not any(d in normalized for d in TITLE_DELIMITERS):
            return False

    if _looks_like_natural_sentence(normalized):
        return False

    return True


# 의미 있는 텍스트인지 판별
def _is_meaningful_text(text: str) -> bool:
    text = _clean_text(text)
    if not text:
        return False
    if len(text) <= 1:
        return False
    if re.fullmatch(r"[\d\s]+", text):
        return False
    return True


def _contains_artist_hint(text: str) -> bool:
    lower = text.lower()
    artist_hints = [
        " feat. ", " feat ", " ft. ", " ft ", " featuring ",
        "prod. ", " prod ", " by ", " x ", " & ", ", "
    ]
    return any(h in f" {lower} " for h in artist_hints)


def _looks_like_artist(text: str) -> bool:
    text = _clean_text(text)
    lower = text.lower()

    if not text:
        return False

    # 아티스트명에 자주 붙는 패턴
    if _contains_artist_hint(text):
        return True

    # 제목보다 아티스트명이 상대적으로 짧은 경우가 많음
    word_count = len(text.split())
    if word_count <= 4:
        return True

    # 전부 대문자/짧은 영어 이름도 artist일 확률이 높음
    if len(text) <= 20 and re.fullmatch(r"[A-Za-z0-9&.,'\- ]+", text):
        return True

    return False


# 곡 정보 생성 + 완성도 계산
def _append_song(results: list[dict], artist: str, title: str):
    artist = _clean_text(artist)
    title = _clean_text(title)

    if not _is_meaningful_text(title):
        return

    artist_ok = _is_meaningful_text(artist)
    title_ok = _is_meaningful_text(title)

    score = 0.0
    if artist_ok:
        score += 0.5
    if title_ok:
        score += 0.5

    results.append({
        "artist": artist if artist_ok else "",
        "title": title,
        "artist_exists": artist_ok,
        "title_exists": title_ok,
        "is_complete": artist_ok and title_ok,
        "completeness_score": score,
    })


# Artist - Title / Title - Artist 판단해서 분리
def _split_pair(text: str):
    separators = [" - ", " – ", " — ", " | ", " / ", " : "]

    for sep in separators:
        if sep in text:
            left, right = text.split(sep, 1)
            left = _clean_text(left)
            right = _clean_text(right)

            if not left or not right:
                return None

            left_artist_like = _looks_like_artist(left)
            right_artist_like = _looks_like_artist(right)

            # Artist - Title
            if left_artist_like and not right_artist_like:
                return {"artist": left, "title": right}

            # Title - Artist
            if right_artist_like and not left_artist_like:
                return {"artist": right, "title": left}

            # 둘 다 애매하면 timestamp 트랙리스트에서 흔한 Artist - Title 우선
            return {"artist": left, "title": right}

    return None


# 비정형 텍스트 → 곡 리스트 파싱
def parse_unstructured_lines_to_json(text: str) -> dict:
    if not text:
        return {"songs": []}

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    temp_pairs = []

    # 1차: 라인에서 left/right 후보만 뽑아두기
    for line in lines:
        if not _is_valid_music_line(line):
            continue

        ts_match = TIMESTAMP_LINE_REGEX.match(line)
        if ts_match:
            body = _clean_text(ts_match.group("body"))
            if not _is_valid_music_line(body):
                continue
            target = body
        else:
            target = _normalize_line(line)

        pair_found = False
        separators = [" - ", " – ", " — ", " | ", " / ", " : "]

        for sep in separators:
            if sep in target:
                left, right = target.split(sep, 1)
                left = _clean_text(left)
                right = _clean_text(right)

                if left and right:
                    temp_pairs.append({
                        "left": left,
                        "right": right,
                    })
                    pair_found = True
                break

        if not pair_found:
            target = _clean_text(target)
            if target:
                temp_pairs.append({
                    "left": "",
                    "right": target,
                })

    # 2차: 반복 빈도 계산
    freq = {}
    for item in temp_pairs:
        left = item.get("left", "")
        right = item.get("right", "")

        if left:
            freq[left] = freq.get(left, 0) + 1
        if right:
            freq[right] = freq.get(right, 0) + 1

    # 3차: 방향 결정
    results = []

    for item in temp_pairs:
        left = item.get("left", "")
        right = item.get("right", "")

        # pair가 아닌 단독 텍스트는 title로만 저장
        if not left and right:
            _append_song(results, artist="", title=right)
            continue

        if not left or not right:
            continue

        left_count = freq.get(left, 0)
        right_count = freq.get(right, 0)

        left_artist_like = _looks_like_artist(left)
        right_artist_like = _looks_like_artist(right)

        # 우선순위 1: 더 자주 반복되는 쪽을 artist로 간주
        if right_count > left_count:
            _append_song(results, artist=right, title=left)
            continue

        if left_count > right_count:
            _append_song(results, artist=left, title=right)
            continue

        # 우선순위 2: artist-like 판정
        if left_artist_like and not right_artist_like:
            _append_song(results, artist=left, title=right)
            continue

        if right_artist_like and not left_artist_like:
            _append_song(results, artist=right, title=left)
            continue

        # 우선순위 3: 애매하면 "제목 - 가수" 형식 우선
        _append_song(results, artist=right, title=left)

    return {"songs": deduplicate_songs(results)}


# 어떤 입력이 와도 songs 구조로 통일
def normalize_song_candidates(data: Any) -> dict:
    if not data:
        return {"songs": []}

    songs = data.get("songs", []) if isinstance(data, dict) else data
    normalized = []

    for item in songs:
        if not isinstance(item, dict):
            continue

        artist = _clean_text(item.get("artist", ""))
        title = _clean_text(item.get("title", ""))

        if not _is_meaningful_text(title):
            continue

        artist_ok = _is_meaningful_text(artist)
        title_ok = _is_meaningful_text(title)

        score = 0.0
        if artist_ok:
            score += 0.5
        if title_ok:
            score += 0.5

        normalized.append({
            "artist": artist if artist_ok else "",
            "title": title,
            "artist_exists": artist_ok,
            "title_exists": title_ok,
            "is_complete": artist_ok and title_ok,
            "completeness_score": score,
        })

    return {"songs": deduplicate_songs(normalized)}


# 중복 곡 제거
def deduplicate_songs(songs: list[dict]) -> list[dict]:
    seen = set()
    unique = []

    for s in songs:
        key = (
            _clean_text(s.get("artist", "")).lower(),
            _clean_text(s.get("title", "")).lower()
        )
        if key in seen:
            continue
        seen.add(key)

        unique.append({
            "artist": s.get("artist", ""),
            "title": s.get("title", ""),
            "artist_exists": s.get("artist_exists", False),
            "title_exists": s.get("title_exists", False),
            "is_complete": s.get("is_complete", False),
            "completeness_score": s.get("completeness_score", 0.0),
        })

    return unique


# timestamp / 패턴 신호 개수 계산
def count_text_signals(text: str) -> dict:
    if not text:
        return {"timestamp_count": 0, "pattern_count": 0}

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    t = sum(1 for l in lines if TIMESTAMP_PREFIX_ONLY_REGEX.search(l))
    p = sum(1 for l in lines if PAIR_REGEX.search(l))

    return {"timestamp_count": t, "pattern_count": p}


# 텍스트 단계 성공 여부 판단 (구조 기반)
def is_text_stage_success(source_text: str, confirmed_tracks: list[dict]) -> bool:
    total = len(confirmed_tracks)
    complete = sum(1 for s in confirmed_tracks if s.get("is_complete"))

    avg = (
        sum(s.get("completeness_score", 0.0) for s in confirmed_tracks) / total
        if total else 0.0
    )

    return (
        total >= MIN_SONG_COUNT
        and complete >= MIN_COMPLETE_SONG_COUNT
        and avg >= MIN_COMPLETENESS_RATIO
    )
