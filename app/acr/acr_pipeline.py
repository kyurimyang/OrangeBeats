import difflib
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List

from app.acr.acr_client import acr_credentials_available, recognize_acr_segment
from app.acr.audio_extractor import download_youtube_audio
from app.acr.segmenter import ACR_SEGMENT_SECONDS, create_audio_segments


def _safe_tmp_dir(prefix: str) -> Path:
    base_dir = Path("tmp") / "fallbacks"
    base_dir.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=base_dir))


def _get_youtube_info(youtube_url: str) -> Dict:
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return {
                "duration": int(info.get("duration") or 0),
                "title": info.get("title") or "",
            }
    except Exception as exc:
        print("[acr] youtube_info_failed =", str(exc))
        return {"duration": 0, "title": ""}


def _deduplicate_acr_songs(songs: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []

    for song in songs:
        artist = str(song.get("artist") or "").strip()
        title = str(song.get("title") or "").strip()
        if not title:
            continue

        duplicate_index = None
        for index, existing in enumerate(merged):
            existing_artist = str(existing.get("artist") or "").strip().lower()
            existing_title = str(existing.get("title") or "").strip().lower()
            title_ratio = difflib.SequenceMatcher(None, title.lower(), existing_title).ratio()
            artist_ratio = difflib.SequenceMatcher(None, artist.lower(), existing_artist).ratio()
            artist_same = artist.lower() == existing_artist
            # ACRCloud는 동일 곡을 세그먼트마다 아티스트 표기를 다르게 반환할 수 있음
            # (피처링 포함/제외, 영문·한글 혼용 등) → 제목 동일 or 둘 다 유사하면 병합
            same_title = title_ratio >= 0.95
            both_similar = title_ratio >= 0.80 and artist_ratio >= 0.35
            if (artist_same and title_ratio >= 0.86) or same_title or both_similar:
                duplicate_index = index
                break

        if duplicate_index is None:
            merged.append(song)
            continue

        existing = merged[duplicate_index]
        if int(song.get("score") or 0) > int(existing.get("score") or 0):
            merged[duplicate_index] = song

    return merged


def extract_songs_with_acr(youtube_url: str) -> Dict:
    work_dir = _safe_tmp_dir("acr_")
    sampled_segments = 0
    recognized_segments = 0

    try:
        info = _get_youtube_info(youtube_url)

        if not acr_credentials_available():
            return {
                "stage": "acr",
                "selected_stage": "acr",
                "success": False,
                "error": "ACRCloud 자격증명이 설정되지 않았습니다. ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET 환경변수를 확인하세요.",
                "songs": [],
                "ocr_used": False,
                "acr_used": False,
                "youtube_title": info.get("title", ""),
                "signals": {
                    "sampled_segments": 0,
                    "recognized_segments": 0,
                },
                "debug": {
                    "skipped": "missing_acrcloud_credentials",
                },
            }

        audio_path = download_youtube_audio(youtube_url, work_dir / "downloads")
        segments = create_audio_segments(audio_path, work_dir / "segments", info.get("duration"))
        sampled_segments = len(segments)

        recognized: List[Dict] = []
        for segment_path in segments:
            song = recognize_acr_segment(segment_path)
            if song:
                recognized_segments += 1
                recognized.append(song)

        return {
            "stage": "acr",
            "selected_stage": "acr",
            "success": True,
            "songs": _deduplicate_acr_songs(recognized),
            "ocr_used": False,
            "acr_used": True,
            "youtube_title": info.get("title", ""),
            "signals": {
                "sampled_segments": sampled_segments,
                "recognized_segments": recognized_segments,
            },
            "debug": {
                "segment_seconds": ACR_SEGMENT_SECONDS,
            },
        }
    except Exception as exc:
        print("[acr] failed =", str(exc))
        return {
            "stage": "acr",
            "selected_stage": "acr",
            "success": False,
            "error": str(exc),
            "songs": [],
            "ocr_used": False,
            "acr_used": False,
            "youtube_title": "",
            "signals": {
                "sampled_segments": sampled_segments,
                "recognized_segments": recognized_segments,
            },
            "debug": {
                "error": str(exc),
            },
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
