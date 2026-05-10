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


def _build_sample_timestamps(duration: float, interval_sec: int, max_frames: Optional[int]) -> List[float]:
    if duration <= 0:
        return []

    interval = max(int(interval_sec), 1)
    regular = [float(t) for t in range(0, max(int(duration), 1), interval)]
    intro = [float(t) for t in range(0, min(90, int(duration)) + 1, 15)]
    outro_start = max(0, int(duration) - 90)
    outro = [float(t) for t in range(outro_start, int(duration), 15)]

    expected_regular_count = math.ceil(duration / interval)
    limit = max_frames if max_frames is not None else expected_regular_count

    selected: List[float] = []
    for timestamp in intro + outro + regular:
        timestamp = min(max(timestamp, 0.0), max(duration - 1.0, 0.0))
        if timestamp in selected:
            continue
        selected.append(timestamp)
        if limit and len(selected) >= limit:
            break
    return sorted(selected)


def _extract_single_frame(video_path: str, output_path: str, timestamp: float) -> None:
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
        "-y",
        "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _extract_interval_frames(
    video_path: str,
    output_dir: str,
    interval_sec: int,
    max_frames: Optional[int],
) -> None:
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
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def extract_frames(
    video_path: str,
    output_dir: str,
    interval_sec: int = 40,
    max_frames: Optional[int] = None,
) -> List[str]:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"video file not found: {video_path}")

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

    try:
        timestamps = _build_sample_timestamps(duration, interval_sec, max_frames)
        if timestamps:
            for index, timestamp in enumerate(timestamps, start=1):
                output_path = os.path.join(output_dir, f"frame_{index:04d}_{int(timestamp):06d}s.jpg")
                _extract_single_frame(video_path, output_path, timestamp)
        else:
            _extract_interval_frames(video_path, output_dir, interval_sec, max_frames)
    except subprocess.CalledProcessError as exc:
        error_message = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        raise RuntimeError(f"frame extraction failed: {error_message}") from exc

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
