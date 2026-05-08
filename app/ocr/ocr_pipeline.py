from __future__ import annotations

import shutil
import tempfile
import difflib
import re
from pathlib import Path
from typing import Any, Dict, Optional

from app.ocr.frame_extractor import extract_frames
from app.ocr.ocr_reader import read_text_from_image
from app.services.youtube_downloader import download_youtube_video

STANDALONE_TIMESTAMP_REGEX = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*$")
LEADING_TIMESTAMP_REGEX = re.compile(r"^\s*(?P<timestamp>(?:\d{1,2}:)?\d{1,2}:\d{2})\s+")
SONG_DELIMITER_REGEX = re.compile(r"\s*[-\u2010-\u2015:/|~\u2022]\s*")
OCR_QUOTE_REGEX = re.compile(r"[`'\"]+")
BROKEN_LINE_REGEX = re.compile(r"^[^\w\uAC00-\uD7A3]+$")

OCR_NOISE_KEYWORDS = {
    "subscribe",
    "youtube",
    "instagram",
    "comment",
    "playlist",
    "tracklist",
    "official",
    "cover",
    "lyrics",
}


def _append_unique_text(texts: list[Dict[str, Any]], seen: set[str], item: Dict[str, Any]) -> None:
    normalized = " ".join(str(item.get("text") or "").split()).lower()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    texts.append(item)


def _normalize_vision_line(line: str) -> str:
    line = str(line or "").strip()
    line = line.replace("\u2018", "'").replace("\u2019", "'")
    line = line.replace("\u201c", '"').replace("\u201d", '"')
    line = line.replace("\u2013", "-").replace("\u2014", "-").replace("\u2015", "-")
    line = OCR_QUOTE_REGEX.sub("", line)
    return " ".join(line.split())


def _vision_line_key(line: str) -> str:
    normalized = _normalize_vision_line(line)
    normalized = LEADING_TIMESTAMP_REGEX.sub("", normalized)
    return normalized.casefold()


def build_vision_text(raw_texts: list[Dict[str, Any]] | list[str]) -> str:
    lines: list[str] = []
    seen_lines: set[str] = set()

    for item in raw_texts:
        text = item.get("text") if isinstance(item, dict) else item
        for raw_line in str(text or "").splitlines():
            line = _normalize_vision_line(raw_line)
            if not line or STANDALONE_TIMESTAMP_REGEX.match(line):
                continue
            key = _vision_line_key(line)
            if key in seen_lines:
                continue
            seen_lines.add(key)
            lines.append(line)

    return "\n".join(lines)


def _strip_leading_timestamp(line: str) -> tuple[str, str]:
    match = LEADING_TIMESTAMP_REGEX.match(line)
    if not match:
        return "", line.strip()
    return match.group("timestamp"), line[match.end():].strip()


def _canonicalize_song_line(line: str) -> str:
    timestamp, body = _strip_leading_timestamp(_normalize_vision_line(line))
    body = SONG_DELIMITER_REGEX.sub(" - ", body, count=1)
    body = " ".join(body.split()).strip()
    return f"{timestamp} {body}".strip() if timestamp else body


def _is_broken_ocr_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < 2:
        return True
    if BROKEN_LINE_REGEX.fullmatch(compact):
        return True
    alnum_hangul = len(re.findall(r"[\w\uAC00-\uD7A3]", compact))
    return alnum_hangul / max(len(compact), 1) < 0.45


def _looks_like_playlist_song_line(line: str) -> bool:
    line = _normalize_vision_line(line)
    if not line or STANDALONE_TIMESTAMP_REGEX.match(line):
        return False
    _timestamp, body = _strip_leading_timestamp(line)
    if _is_broken_ocr_text(body):
        return False
    lower = body.casefold()
    if any(keyword in lower for keyword in OCR_NOISE_KEYWORDS) and not SONG_DELIMITER_REGEX.search(body):
        return False
    if len(body) > 90:
        return False
    if not SONG_DELIMITER_REGEX.search(body):
        return False
    left, right = SONG_DELIMITER_REGEX.split(body, 1)
    return not _is_broken_ocr_text(left) and not _is_broken_ocr_text(right)


def _consistency_score(lines: list[str]) -> float:
    song_lines = [line for line in lines if _looks_like_playlist_song_line(line)]
    if not song_lines:
        return 0.0
    timestamp_count = sum(1 for line in song_lines if _strip_leading_timestamp(line)[0])
    delimiter_count = sum(1 for line in song_lines if SONG_DELIMITER_REGEX.search(_strip_leading_timestamp(line)[1]))
    timestamp_ratio = timestamp_count / len(song_lines)
    delimiter_ratio = delimiter_count / len(song_lines)
    return round((timestamp_ratio * 0.45) + (delimiter_ratio * 0.55), 4)


def _best_song_run(lines: list[str]) -> list[str]:
    best: list[str] = []
    current: list[str] = []
    for line in lines:
        if _looks_like_playlist_song_line(line):
            current.append(line)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []
    if len(best) >= 2:
        return best
    return [line for line in lines if _looks_like_playlist_song_line(line)]


def score_ocr_block(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_text = str(item.get("text") or "")
    lines = [
        _normalize_vision_line(line)
        for line in raw_text.splitlines()
        if _normalize_vision_line(line) and not STANDALONE_TIMESTAMP_REGEX.match(_normalize_vision_line(line))
    ]
    song_lines = [line for line in lines if _looks_like_playlist_song_line(line)]
    selected_lines = [_canonicalize_song_line(line) for line in _best_song_run(lines)]
    timestamp_count = sum(1 for line in selected_lines if _strip_leading_timestamp(line)[0])
    delimiter_count = sum(1 for line in selected_lines if SONG_DELIMITER_REGEX.search(_strip_leading_timestamp(line)[1]))
    density = len(song_lines) / max(len(lines), 1)
    consistency = _consistency_score(selected_lines)
    score = (
        timestamp_count * 5.0
        + delimiter_count * 3.0
        + len(selected_lines) * 4.0
        + density * 3.0
        + consistency * 4.0
    )
    return {
        "frame_index": item.get("frame_index"),
        "frame_path": item.get("frame_path", ""),
        "text": raw_text,
        "normalized_text": "\n".join(lines),
        "selected_text": "\n".join(selected_lines),
        "score": round(score, 4),
        "song_line_count": len(selected_lines),
        "timestamp_count": timestamp_count,
        "delimiter_count": delimiter_count,
        "text_density": round(density, 4),
        "format_consistency": consistency,
        "lines": lines,
        "selected_lines": selected_lines,
    }


def select_representative_ocr_block(raw_texts: list[Dict[str, Any]]) -> Dict[str, Any]:
    blocks = [score_ocr_block(item) for item in raw_texts]
    viable = [
        block for block in blocks
        if block["song_line_count"] >= 2 or (block["timestamp_count"] >= 1 and block["delimiter_count"] >= 1)
    ]
    selected = max(viable or blocks, key=lambda block: (block["score"], block["song_line_count"]), default={})

    # viable 블록들의 selected_lines만 합산 — combined_text(전 프레임 raw)와 달리
    # _looks_like_playlist_song_line을 통과한 정제된 라인만 포함된다.
    merged_lines: list[str] = []
    merged_keys: list[str] = []
    seen_keys: set[str] = set()
    for block in sorted(viable or blocks, key=lambda b: b["score"], reverse=True):
        for line in block.get("selected_lines", []):
            key = _vision_line_key(line)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_keys.append(key)
            merged_lines.append(line)

    return {
        "blocks": blocks,
        "selected_block": selected,
        "selected_text": str(selected.get("selected_text") or selected.get("normalized_text") or "").strip(),
        "merged_viable_text": "\n".join(merged_lines),
    }


def merge_near_duplicate_songs(songs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    for song in songs:
        artist = str(song.get("artist") or "").strip()
        title = str(song.get("title") or "").strip()
        if not title or _is_broken_ocr_text(title):
            continue
        key = f"{artist.casefold()} - {title.casefold()}"
        duplicate_index = None
        for index, existing in enumerate(merged):
            existing_artist = str(existing.get("artist") or "").casefold()
            existing_title = str(existing.get("title") or "").casefold()
            existing_key = f"{existing_artist} - {existing_title}"
            artist_same = artist.casefold() == existing_artist
            title_ratio = difflib.SequenceMatcher(None, title.casefold(), existing_title).ratio()
            full_ratio = difflib.SequenceMatcher(None, key, existing_key).ratio()
            artist_ratio = difflib.SequenceMatcher(None, artist.casefold(), existing_artist).ratio()
            # OCR이 같은 화면을 다른 프레임에서 읽어 아티스트/제목이 약간씩 달라진 경우를 병합:
            # - same_title: 제목이 동일하면 아티스트 오인식 변형으로 간주
            # - both_ocr_similar: 제목과 아티스트가 모두 유사하면 OCR 변형으로 간주
            same_title = title_ratio >= 0.95
            both_ocr_similar = title_ratio >= 0.80 and artist_ratio >= 0.35
            if (artist_same and title_ratio >= 0.86) or full_ratio >= 0.90 or same_title or both_ocr_similar:
                duplicate_index = index
                break
        if duplicate_index is None:
            merged.append(song)
            continue
        existing = merged[duplicate_index]
        existing_raws = list(existing.get("raw_variants") or [existing.get("raw", "")])
        existing_raws.append(song.get("raw", ""))
        existing["raw_variants"] = [raw for raw in dict.fromkeys(existing_raws) if raw]
        if len(title) > len(str(existing.get("title") or "")):
            existing.update(song)
            existing["raw_variants"] = [raw for raw in dict.fromkeys(existing_raws) if raw]
    return merged


def run_ocr_pipeline(
    youtube_url: Optional[str] = None,
    *,
    video_path: Optional[str] = None,
    work_dir: Optional[str] = None,
    interval_sec: int = 40,
    max_frames: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Extract sampled frames from a video and read visible playlist text with OpenAI vision.

    The fallback caller passes an already downloaded video_path. youtube_url is kept for
    direct/manual use and downloads the video into the OCR work directory.
    """
    if not video_path and not youtube_url:
        raise ValueError("Either video_path or youtube_url is required for OCR.")

    owns_work_dir = work_dir is None
    base_dir = Path(work_dir or tempfile.mkdtemp(prefix="ocr_pipeline_"))
    download_dir = base_dir / "downloads"
    frame_dir = base_dir / "frames"
    raw_texts: list[Dict[str, Any]] = []
    errors: list[Dict[str, str]] = []
    seen_texts: set[str] = set()

    try:
        print("[ocr-pipeline] start interval_sec =", interval_sec, "max_frames =", max_frames)
        base_dir.mkdir(parents=True, exist_ok=True)

        resolved_video_path = video_path
        if not resolved_video_path:
            resolved_video_path = download_youtube_video(str(youtube_url), output_dir=str(download_dir))

        frames = extract_frames(
            video_path=str(resolved_video_path),
            output_dir=str(frame_dir),
            interval_sec=interval_sec,
            max_frames=max_frames,
        )
        print("[ocr-pipeline] frame extraction end frame_count =", len(frames))

        print("[ocr-pipeline] vision OCR start")
        for index, frame_path in enumerate(frames):
            try:
                print(f"[ocr-pipeline] vision frame {index + 1}/{len(frames)} start")
                text = read_text_from_image(frame_path).strip()
                print(f"[ocr-pipeline] vision frame {index + 1}/{len(frames)} done text_len={len(text)}")
                if text:
                    _append_unique_text(
                        raw_texts,
                        seen_texts,
                        {
                            "frame_index": index,
                            "frame_path": frame_path,
                            "text": text,
                        },
                    )
            except Exception as exc:
                errors.append({"frame_path": frame_path, "error": str(exc)})
                print(f"[ocr-pipeline] vision frame {index + 1}/{len(frames)} failed error={exc}")
        print("[ocr-pipeline] vision OCR end unique_text_count =", len(raw_texts))
        combined_text = build_vision_text(raw_texts)
        block_selection = select_representative_ocr_block(raw_texts)
        selected_text = block_selection.get("selected_text") or combined_text
        merged_viable_text = block_selection.get("merged_viable_text") or ""
        print("[ocr-pipeline] combined_text length =", len(combined_text))
        print("[ocr-pipeline] selected_text length =", len(selected_text))
        print("[ocr-pipeline] merged_viable_text length =", len(merged_viable_text))

        return {
            "success": True,
            "status": "success",
            "video_path": str(resolved_video_path),
            "frame_count": len(frames),
            "raw_text_count": len(raw_texts),
            "raw_texts": raw_texts,
            "ocr_blocks": block_selection.get("blocks", []),
            "selected_ocr_block": block_selection.get("selected_block", {}),
            "errors": errors,
            "combined_text": combined_text,
            "selected_text": selected_text,
            "merged_viable_text": merged_viable_text,
        }
    finally:
        if owns_work_dir:
            shutil.rmtree(base_dir, ignore_errors=True)
