import os
from pathlib import Path
from typing import Dict, List

from app.ocr.frame_extractor import extract_frames
from app.ocr.image_preprocessor import preprocess_image
from app.ocr.ocr_reader import read_text
from app.ocr.ocr_parser import (
    deduplicate_candidates,
    looks_like_song_line,
    parse_song_candidate,
)


def run_ocr_pipeline(
    video_path: str,
    work_dir: str = "./tmp/ocr",
    interval_sec: int = 30,
    max_frames: int | None = None,
) -> Dict:
    """
    OCR 전체 파이프라인:
    영상 -> 프레임 추출 -> 이미지 전처리 -> OCR -> 곡 후보 파싱

    Args:
        video_path: 로컬 영상 파일 경로
        work_dir: 작업용 폴더
        interval_sec: 몇 초마다 프레임 추출할지

    Returns:
        dict 형태의 OCR 결과
    """
    base_dir = Path(work_dir)
    frames_dir = base_dir / "frames"
    processed_dir = base_dir / "processed"

    frames_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    frames = extract_frames(
        video_path=video_path,
        output_dir=str(frames_dir),
        interval_sec=interval_sec,
        max_frames=max_frames,
    )

    raw_texts: List[Dict] = []
    song_candidates: List[Dict] = []

    for frame_path in frames:
        filename = os.path.basename(frame_path)
        processed_path = str(processed_dir / filename)

        preprocess_image(frame_path, processed_path)
        texts = read_text(processed_path)

        for text in texts:
            raw_texts.append(
                {
                    "frame": frame_path,
                    "text": text,
                }
            )

            if looks_like_song_line(text):
                parsed = parse_song_candidate(text)
                if parsed:
                    parsed["frame"] = frame_path
                    song_candidates.append(parsed)

    song_candidates = deduplicate_candidates(song_candidates)

    return {
        "status": "success",
        "video_path": video_path,
        "frame_count": len(frames),
        "raw_text_count": len(raw_texts),
        "raw_texts": raw_texts,
        "song_candidates": song_candidates,
    }
