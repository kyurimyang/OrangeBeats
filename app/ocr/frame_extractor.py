import math
import os
import subprocess
from pathlib import Path
from typing import List, Optional


def _get_video_duration(video_path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip() or 0)
    except Exception:
        return 0.0


def extract_frames(
    video_path: str,
    output_dir: str,
    interval_sec: int = 40,
    max_frames: Optional[int] = None,
) -> List[str]:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    duration = _get_video_duration(video_path)
    expected_frame_count = math.ceil(duration / interval_sec) if duration > 0 else None
    effective_max = max_frames if max_frames is not None else expected_frame_count

    print(
        f"[frame-extractor] duration={duration:.1f}s"
        f" interval_sec={interval_sec}"
        f" expected_frame_count={expected_frame_count}"
        f" max_frames={max_frames}"
    )

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/{interval_sec}",
        "-q:v", "2",
    ]

    if max_frames is not None:
        cmd.extend(["-frames:v", str(max_frames)])

    cmd.extend([output_pattern, "-y", "-loglevel", "error"])

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"프레임 추출 실패: {error_message}") from e

    frames = sorted(
        str(Path(output_dir) / filename)
        for filename in os.listdir(output_dir)
        if filename.lower().endswith(".jpg")
    )

    print(
        f"[frame-extractor] actual_frame_count={len(frames)}"
        f" expected_frame_count={expected_frame_count}"
        f" effective_max={effective_max}"
    )
    return frames
