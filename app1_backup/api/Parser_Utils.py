import json
import re
from typing import Any
from backend.constants.Pipeline_Paramas import MIN_PATTERN, MIN_TIMESTAMP, MIN_TRACKS

TIMESTAMP_WITH_TEXT_RE = re.compile(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$")
TIMESTAMP_ONLY_RE = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*$")
SONG_PATTERN_RE = re.compile(r".+\s[-|]\s.+")


def parse_json_from_text(raw_text: str) -> Any:
    """
    LLM 응답 텍스트에서 JSON 객체/배열을 추출해 파싱한다.
    """
    text = raw_text.strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced[0].strip()

    candidates = [text]
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidates.append(text[obj_start : obj_end + 1])

    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidates.append(text[arr_start : arr_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError("유효한 JSON을 찾지 못했습니다.")


def _append_song(
    songs: list[dict[str, str]],
    seen: set[tuple[str, str]],
    artist: str,
    title: str,
) -> None:
    artist = artist.strip() or "unknown"
    title = title.strip()
    if not title:
        return

    key = (artist.lower(), title.lower())
    if key in seen:
        return

    seen.add(key)
    songs.append({"artist": artist, "title": title})


def _split_pair(left: str, right: str) -> tuple[str, str]:
    """
    기본 규칙: Song - Artist 패턴을 우선으로 보되,
    artist 힌트가 더 강한 쪽은 artist로 보정한다.
    """
    left = left.strip()
    right = right.strip()

    artist_hints = (" feat", " ft", "&", ",", " x ")
    left_is_artist = any(h in left.lower() for h in artist_hints)
    right_is_artist = any(h in right.lower() for h in artist_hints)

    if left_is_artist and not right_is_artist:
        return left, right
    if right_is_artist and not left_is_artist:
        return right, left

    # 기본값: Title - Artist
    return right, left


def parse_unstructured_lines_to_json(lines: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    댓글/설명란 등 비정형 라인 목록을 songs JSON 구조로 변환한다.
    """
    songs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    cleaned = [line.strip(" -\t") for line in lines]

    i = 0
    while i < len(cleaned):
        line = cleaned[i]
        if not line:
            i += 1
            continue

        # 00:00 Song - Artist / 00:00 Artist - Song / 00:00 Song
        m = TIMESTAMP_WITH_TEXT_RE.match(line)
        if m:
            content = m.group(2).strip()
            if " - " in content:
                left, right = content.split(" - ", 1)
                artist, title = _split_pair(left, right)
                _append_song(songs, seen, artist, title)
            else:
                _append_song(songs, seen, "unknown", content)
            i += 1
            continue

        # 00:00 다음 줄(들)에 Song / Artist가 분리된 경우
        if TIMESTAMP_ONLY_RE.match(line):
            block: list[str] = []
            j = i + 1
            while j < len(cleaned):
                candidate = cleaned[j]
                if not candidate:
                    j += 1
                    continue
                if TIMESTAMP_ONLY_RE.match(candidate) or TIMESTAMP_WITH_TEXT_RE.match(candidate):
                    break
                block.append(candidate)
                if len(block) >= 2:
                    break
                j += 1

            if len(block) == 2:
                artist, title = _split_pair(block[0], block[1])
                _append_song(songs, seen, artist, title)
                i = j
                continue
            if len(block) == 1:
                _append_song(songs, seen, "unknown", block[0])
                i = j
                continue

            i += 1
            continue

        # 일반 Song - Artist / Artist - Song
        if " - " in line:
            left, right = line.split(" - ", 1)
            artist, title = _split_pair(left, right)
            _append_song(songs, seen, artist, title)
            i += 1
            continue

        # 그 외는 제목 후보로 저장
        _append_song(songs, seen, "unknown", line)
        i += 1

    return {"songs": songs}


def normalize_song_candidates(data: Any) -> dict[str, list[dict[str, str]]]:
    """
    다양한 입력 형태(dict/list/string)를 songs JSON 구조로 정규화한다.
    """
    if isinstance(data, dict) and isinstance(data.get("songs"), list):
        songs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in data["songs"]:
            if isinstance(item, dict):
                artist = str(item.get("artist", "unknown")).strip() or "unknown"
                title = str(item.get("title", "")).strip()
                _append_song(songs, seen, artist, title)
            elif isinstance(item, str):
                parsed = parse_unstructured_lines_to_json([item])["songs"]
                for song in parsed:
                    _append_song(songs, seen, song["artist"], song["title"])
        return {"songs": songs}

    if isinstance(data, list):
        return parse_unstructured_lines_to_json([str(x) for x in data])

    if isinstance(data, str):
        return parse_unstructured_lines_to_json([data])

    return {"songs": []}


def count_text_signals(lines: list[str]) -> dict[str, int]:
    """
    설명란/댓글 텍스트의 신호량을 계산한다.
    - timestamp_count: 00:00, 1:23, 01:02:03 같은 패턴 수
    - pattern_count: Artist - Song / Song | Artist 같은 패턴 수
    """
    timestamp_count = 0
    pattern_count = 0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if TIMESTAMP_ONLY_RE.match(line) or TIMESTAMP_WITH_TEXT_RE.match(line):
            timestamp_count += 1
        if SONG_PATTERN_RE.match(line):
            pattern_count += 1
    return {"timestamp_count": timestamp_count, "pattern_count": pattern_count}


def is_text_stage_success(lines: list[str], confirmed_tracks: int) -> bool:
    """
    설명란/댓글 단계 성공 여부 판단:
    - timestamp >= MIN_TIMESTAMP 또는 pattern >= MIN_PATTERN
    - 그리고 확정 곡 >= MIN_TRACKS
    """
    signals = count_text_signals(lines)
    has_signal = (
        signals["timestamp_count"] >= MIN_TIMESTAMP
        or signals["pattern_count"] >= MIN_PATTERN
    )
    return has_signal and confirmed_tracks >= MIN_TRACKS
