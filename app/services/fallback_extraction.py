from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Dict

from app.ocr.ocr_pipeline import merge_near_duplicate_songs, run_ocr_pipeline
from app.services.text_analysis import analyze_text_block
from app.services.youtube_downloader import download_youtube_video

OCR_INTERVAL_SECONDS = 40  # extract one frame every N seconds, full video

# Below these thresholds, mark as partial_success with a warning
_INSUFFICIENT_TEXT_CHARS = 100
_INSUFFICIENT_RAW_COUNT = 3


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
                "video_id": info.get("id") or "",
            }
    except Exception as exc:
        print("[fallback] youtube_info_failed =", str(exc))
        return {"duration": 0, "title": ""}


def extract_songs_with_ocr(youtube_url: str) -> Dict:
    work_dir = _safe_tmp_dir("ocr_")
    sampled_frames = 0
    vision_text = ""
    analysis_result: Dict = {}

    try:
        print("[ocr] start extract_songs_with_ocr url =", youtube_url)
        info = _get_youtube_info(youtube_url)
        duration = int(info.get("duration") or 0)
        expected_frame_count = math.ceil(duration / OCR_INTERVAL_SECONDS) if duration > 0 else None

        print(
            "[ocr] sampling plan"
            f" duration={duration}s"
            f" interval_sec={OCR_INTERVAL_SECONDS}"
            f" expected_frame_count={expected_frame_count}"
        )

        video_path = download_youtube_video(youtube_url, output_dir=str(work_dir / "downloads"))
        print("[ocr] download end video_path =", video_path)

        print("[ocr] frame+vision start")
        ocr_result = run_ocr_pipeline(
            video_path=video_path,
            work_dir=str(work_dir / "ocr"),
            interval_sec=OCR_INTERVAL_SECONDS,
            max_frames=None,
        )

        actual_frame_count = int(ocr_result.get("frame_count") or 0)
        raw_text_count = int(ocr_result.get("raw_text_count") or 0)
        print(
            "[ocr] frame+vision end"
            f" duration={duration}s"
            f" interval_sec={OCR_INTERVAL_SECONDS}"
            f" expected_frame_count={expected_frame_count}"
            f" actual_frame_count={actual_frame_count}"
            f" raw_text_count={raw_text_count}"
        )

        sampled_frames = actual_frame_count
        merged_viable_text = str(ocr_result.get("merged_viable_text") or "").strip()
        raw_vision_text = str(ocr_result.get("combined_text") or "").strip()
        selected_text = str(ocr_result.get("selected_text") or "").strip()
        # merged_viable_text: viable 블록들의 selected_lines만 합산 — OCR 노이즈 프레임 제외
        # combined_text: 전 프레임 raw 텍스트 합산 — 범위는 넓지만 OCR 변형 포함
        # selected_text: 단일 최고점 블록 — 곡 누락 위험
        vision_text = merged_viable_text or raw_vision_text or selected_text
        print("[ocr] vision_text length =", len(vision_text))
        print("[ocr] parser start")
        analysis_result = analyze_text_block(vision_text, stage="vision")
        print("[ocr] parser end method =", analysis_result.get("method"), "success =", analysis_result.get("success"))
        songs = merge_near_duplicate_songs(analysis_result.get("songs", []))
        print("[ocr] songs count =", len(songs))

        has_songs = bool(songs)
        insufficient_text = len(vision_text) < _INSUFFICIENT_TEXT_CHARS or raw_text_count < _INSUFFICIENT_RAW_COUNT
        partial_success = has_songs and insufficient_text
        warning = (
            "화면에서 읽힌 텍스트가 부족해 곡 목록이 완전하지 않을 수 있습니다."
            if partial_success else ""
        )

        response_payload = {
            "video_id": info.get("video_id", ""),
            "youtube_title": info.get("title", ""),
            "selected_stage": "ocr",
            "text_stage": "vision",
            "success": has_songs,
            "partial_success": partial_success,
            "warning": warning,
            "songs": songs,
            "ocr_used": True,
            "acr_used": False,
            "signals": {
                "duration": duration,
                "interval_sec": OCR_INTERVAL_SECONDS,
                "expected_frame_count": expected_frame_count,
                "actual_frame_count": actual_frame_count,
                "sampled_frames": sampled_frames,
                "raw_text_count": raw_text_count,
                "vision_text_lines": len(vision_text.splitlines()) if vision_text else 0,
                "raw_vision_text_lines": len(raw_vision_text.splitlines()) if raw_vision_text else 0,
                "selected_ocr_block_score": (ocr_result.get("selected_ocr_block") or {}).get("score", 0),
                **analysis_result.get("signals", {}),
            },
            "metrics": analysis_result.get("metrics", {}),
            "debug": {
                "vision": {
                    "raw_text": vision_text,
                    "raw_ocr_text": raw_vision_text,
                    "ocr_blocks": ocr_result.get("ocr_blocks", []),
                    "selected_ocr_block": ocr_result.get("selected_ocr_block", {}),
                    "method": analysis_result.get("method", ""),
                    "success": analysis_result.get("success", False),
                    "songs": songs,
                    "signals": analysis_result.get("signals", {}),
                    "metrics": analysis_result.get("metrics", {}),
                    "duration": duration,
                    "interval_sec": OCR_INTERVAL_SECONDS,
                    "expected_frame_count": expected_frame_count,
                    "actual_frame_count": actual_frame_count,
                    "raw_text_count": raw_text_count,
                    "insufficient_text": insufficient_text,
                    "errors": ocr_result.get("errors", []),
                },
            },
        }
        print("[ocr] return payload keys =", list(response_payload.keys()), "songs =", len(songs))
        return response_payload
    except Exception as exc:
        print("[fallback] ocr_failed =", str(exc))
        return {
            "video_id": "",
            "youtube_title": "",
            "selected_stage": "ocr",
            "text_stage": "vision",
            "success": False,
            "songs": [],
            "ocr_used": True,
            "acr_used": False,
            "signals": {
                "sampled_frames": sampled_frames,
                "vision_text_lines": len(vision_text.splitlines()) if vision_text else 0,
            },
            "metrics": analysis_result.get("metrics", {}),
            "debug": {
                "vision": {
                    "raw_text": vision_text,
                    "error": str(exc),
                    **analysis_result,
                },
            },
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
