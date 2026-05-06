from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from app.ocr.frame_extractor import extract_frames
from app.ocr.ocr_reader import read_text_from_image
from app.services.youtube_downloader import download_youtube_video


def _append_unique_text(texts: list[Dict[str, Any]], seen: set[str], item: Dict[str, Any]) -> None:
    normalized = " ".join(str(item.get("text") or "").split()).lower()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    texts.append(item)


def run_ocr_pipeline(
    youtube_url: Optional[str] = None,
    *,
    video_path: Optional[str] = None,
    work_dir: Optional[str] = None,
    interval_sec: int = 30,
    max_frames: Optional[int] = 15,
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

        for index, frame_path in enumerate(frames):
            try:
                text = read_text_from_image(frame_path).strip()
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
                print(f"OCR frame failed: {frame_path} / {exc}")

        return {
            "success": True,
            "status": "success",
            "video_path": str(resolved_video_path),
            "frame_count": len(frames),
            "raw_text_count": len(raw_texts),
            "raw_texts": raw_texts,
            "errors": errors,
            "combined_text": "\n".join(item["text"] for item in raw_texts),
        }
    finally:
        if owns_work_dir:
            shutil.rmtree(base_dir, ignore_errors=True)
