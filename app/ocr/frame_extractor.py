import os
import subprocess
from pathlib import Path
from typing import List


def extract_frames(
    video_path: str,
    output_dir: str,
    interval_sec: int = 30,
    max_frames: int | None = None,
) -> List[str]:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/{interval_sec}",
        "-q:v", "2",
    ]

    if max_frames:
        cmd.extend(["-frames:v", str(max_frames)])

    cmd.extend([
        output_pattern,
        "-y",
        "-loglevel", "error",
    ])

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

    return frames
