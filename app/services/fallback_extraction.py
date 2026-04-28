from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List

from app.clients.openai_client import extract_songs_with_llm
from app.ocr.ocr_pipeline import run_ocr_pipeline
from app.parsers.song_parser import normalize_song_candidates, parse_json_from_text
from app.services.youtube_downloader import download_youtube_video

OCR_MAX_FRAMES = 15
MIN_SAMPLE_INTERVAL_SECONDS = 30
MAX_SAMPLE_INTERVAL_SECONDS = 60


def _safe_tmp_dir(prefix: str) -> Path:
    base_dir = Path("tmp") / "fallbacks"
    base_dir.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=base_dir))


def _sample_interval(duration_seconds: int | None, max_samples: int) -> int:
    if not duration_seconds or duration_seconds <= 0:
        return MIN_SAMPLE_INTERVAL_SECONDS

    interval = math.ceil(duration_seconds / max_samples)
    return max(MIN_SAMPLE_INTERVAL_SECONDS, min(MAX_SAMPLE_INTERVAL_SECONDS, interval))


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
        print("[fallback] youtube_info_failed =", str(exc))
        return {"duration": 0, "title": ""}


def _songs_from_text_blocks(text_blocks: List[str]) -> List[Dict]:
    try:
        llm_raw = extract_songs_with_llm(text_blocks)
        llm_json = parse_json_from_text(llm_raw)
        return normalize_song_candidates(llm_json).get("songs", [])
    except Exception as exc:
        print("[fallback] llm_song_extract_failed =", str(exc))
        return []


def extract_songs_with_ocr(youtube_url: str) -> Dict:
    work_dir = _safe_tmp_dir("ocr_")
    sampled_frames = 0
    text_blocks: List[str] = []

    try:
        info = _get_youtube_info(youtube_url)
        interval_sec = _sample_interval(info.get("duration"), OCR_MAX_FRAMES)
        video_path = download_youtube_video(youtube_url, output_dir=str(work_dir / "downloads"))

        ocr_result = run_ocr_pipeline(
            video_path=video_path,
            work_dir=str(work_dir / "ocr"),
            interval_sec=interval_sec,
            max_frames=OCR_MAX_FRAMES,
        )
        sampled_frames = int(ocr_result.get("frame_count") or 0)
        text_blocks = [
            str(item.get("text") or "").strip()
            for item in ocr_result.get("raw_texts", [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]

        return {
            "stage": "ocr",
            "selected_stage": "ocr",
            "success": True,
            "songs": _songs_from_text_blocks(text_blocks),
            "ocr_used": True,
            "acr_used": False,
            "youtube_title": info.get("title", ""),
            "signals": {
                "sampled_frames": sampled_frames,
                "text_blocks": len(text_blocks),
            },
            "debug": {
                "ocr": {
                    "interval_sec": interval_sec,
                    "raw_text_count": len(text_blocks),
                },
            },
        }
    except Exception as exc:
        print("[fallback] ocr_failed =", str(exc))
        return {
            "stage": "ocr",
            "selected_stage": "ocr",
            "success": True,
            "songs": [],
            "ocr_used": True,
            "acr_used": False,
            "youtube_title": "",
            "signals": {
                "sampled_frames": sampled_frames,
                "text_blocks": len(text_blocks),
            },
            "debug": {
                "error": str(exc),
            },
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
