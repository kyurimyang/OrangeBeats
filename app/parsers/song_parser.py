# 텍스트/JSON 파싱, 중복 제거, 성공 판정
# 설명란/LLM 결과를 곡 리스트로 정리

import json
import re
from typing import Any

from app.constants.pipeline_params import MIN_PATTERN, MIN_TIMESTAMP, MIN_TRACKS


def parse_json_from_text(text: str) -> dict:
    """
    LLM 응답에서 JSON만 추출.
    실패하면 {"songs": []} 반환.
    """
    if not text:
        return {"songs": []}

    text = text.strip()

    # ```json ... ``` 코드블록 제거
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"songs": []}

    json_str = match.group(0)

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict) and "songs" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    return {"songs": []}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -–—:|/").strip()


def _append_song(results: list[dict], artist: str, title: str):
    artist = _clean_text(artist)
    title = _clean_text(title)

    if not title:
        return

    if not artist:
        artist = "unknown"

    results.append({
        "artist": artist,
        "title": title,
    })


def _split_pair(text: str) -> tuple[str, str] | None:
    """
    Song - Artist 같은 단순 분리
    """
    separators = [" - ", " – ", " — ", " | ", " / ", ":"]
    for sep in separators:
        if sep in text:
            left, right = text.split(sep, 1)
            left = _clean_text(left)
            right = _clean_text(right)
            if left and right:
                return left, right
    return None


def parse_unstructured_lines_to_json(text: str) -> dict:
    """
    설명란 같은 비정형 텍스트를 규칙 기반으로 파싱
    """
    if not text:
        return {"songs": []}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    results: list[dict] = []

    timestamp_regex = re.compile(r"^(?P<ts>\d{1,2}:\d{2})(?::\d{2})?\s+(?P<body>.+)$")

    for line in lines:
        # 00:00 Song - Artist
        ts_match = timestamp_regex.match(line)
        if ts_match:
            body = ts_match.group("body").strip()
            pair = _split_pair(body)

            if pair:
                left, right = pair
                # 일단 Song - Artist 기준으로 저장
                _append_song(results, artist=right, title=left)
            else:
                _append_song(results, artist="unknown", title=body)
            continue

        # 일반 Song - Artist
        pair = _split_pair(line)
        if pair:
            left, right = pair
            _append_song(results, artist=right, title=left)

    return {"songs": deduplicate_songs(results)}


def normalize_song_candidates(data: Any) -> dict:
    """
    어떤 입력이 와도 {"songs": [...]} 형태로 정리
    """
    if not data:
        return {"songs": []}

    if isinstance(data, dict):
        songs = data.get("songs", [])
    elif isinstance(data, list):
        songs = data
    else:
        return {"songs": []}

    normalized = []
    for item in songs:
        if not isinstance(item, dict):
            continue

        artist = _clean_text(str(item.get("artist", "")))
        title = _clean_text(str(item.get("title", "")))

        if not title:
            continue

        normalized.append({
            "artist": artist if artist else "unknown",
            "title": title,
        })

    return {"songs": deduplicate_songs(normalized)}


def deduplicate_songs(songs: list[dict]) -> list[dict]:
    seen = set()
    unique = []

    for song in songs:
        artist = _clean_text(song.get("artist", "")).lower()
        title = _clean_text(song.get("title", "")).lower()

        if not title:
            continue

        key = (artist, title)
        if key in seen:
            continue

        seen.add(key)
        unique.append({
            "artist": song.get("artist", "unknown"),
            "title": song.get("title", ""),
        })

    return unique


def count_text_signals(text: str) -> dict:
    """
    텍스트 안에 곡 목록처럼 보이는 신호 계산
    """
    if not text:
        return {
            "timestamp_count": 0,
            "pattern_count": 0,
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    timestamp_count = 0
    pattern_count = 0

    timestamp_regex = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+")
    pair_regex = re.compile(r".+\s[-–—|/]\s.+")

    for line in lines:
        if timestamp_regex.search(line):
            timestamp_count += 1
        if pair_regex.search(line):
            pattern_count += 1

    return {
        "timestamp_count": timestamp_count,
        "pattern_count": pattern_count,
    }


def is_text_stage_success(source_text: str, confirmed_tracks: list[dict]) -> bool:
    """
    현재 단계(설명란/댓글)가 충분히 성공했는지 판단
    """
    signals = count_text_signals(source_text)
    track_count = len(confirmed_tracks)

    if track_count >= MIN_TRACKS:
        return True

    if signals["timestamp_count"] >= MIN_TIMESTAMP:
        return True

    if signals["pattern_count"] >= MIN_PATTERN and track_count >= 2:
        return True

    return False