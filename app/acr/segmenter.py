import math
import subprocess
from pathlib import Path
from typing import List

ACR_MAX_SEGMENTS = 20
ACR_SEGMENT_SECONDS = 10
MIN_SAMPLE_INTERVAL_SECONDS = 30
MAX_SAMPLE_INTERVAL_SECONDS = 180  # 3분 상한 — 60분 영상도 20개 세그먼트로 전체 커버


def sample_interval(duration_seconds: int | None, max_samples: int) -> int:
    if not duration_seconds or duration_seconds <= 0:
        return MIN_SAMPLE_INTERVAL_SECONDS

    interval = math.ceil(duration_seconds / max_samples)
    return max(MIN_SAMPLE_INTERVAL_SECONDS, min(MAX_SAMPLE_INTERVAL_SECONDS, interval))


def create_audio_segments(audio_path: Path, output_dir: Path, duration_seconds: int | None) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    interval_sec = sample_interval(duration_seconds, ACR_MAX_SEGMENTS)
    segments: List[Path] = []

    for index in range(ACR_MAX_SEGMENTS):
        start_sec = index * interval_sec
        if duration_seconds and start_sec >= duration_seconds:
            break

        segment_path = output_dir / f"segment_{index:02d}.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_sec),
            "-i",
            str(audio_path),
            "-t",
            str(ACR_SEGMENT_SECONDS),
            "-ac",
            "1",
            "-ar",
            "44100",
            str(segment_path),
            "-loglevel",
            "error",
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if segment_path.exists() and segment_path.stat().st_size > 0:
                segments.append(segment_path)
        except subprocess.CalledProcessError as exc:
            error_message = exc.stderr.decode("utf-8", errors="ignore")
            print("[acr] segment_failed =", error_message)

    return segments
