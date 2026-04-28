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
    best_by_key: Dict[tuple[str, str], Dict] = {}

    for song in songs:
        artist = str(song.get("artist") or "").strip()
        title = str(song.get("title") or "").strip()
        if not title:
            continue

        key = (artist.lower(), title.lower())
        previous = best_by_key.get(key)
        if previous and int(previous.get("score") or 0) >= int(song.get("score") or 0):
            continue
        best_by_key[key] = song

    return list(best_by_key.values())


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
                "success": True,
                "songs": [],
                "ocr_used": False,
                "acr_used": True,
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
            "success": True,
            "songs": [],
            "ocr_used": False,
            "acr_used": True,
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
