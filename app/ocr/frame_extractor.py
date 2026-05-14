import math
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from app.utils.ffmpeg import resolve_ffmpeg_binary

_SHOWINFO_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


def _get_video_duration(video_path: str) -> float:
    try:
        ffprobe_binary = resolve_ffmpeg_binary("ffprobe")
        result = subprocess.run(
            [
                ffprobe_binary, "-v", "error",
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


def detect_scene_change_timestamps(
    video_path: str,
    threshold: float = 0.35,
    max_scenes: int = 60,
) -> List[float]:
    """
    ffmpeg select+showinfo 필터로 장면 전환 시점(초)을 반환한다.

    threshold: 0.0~1.0, 높을수록 큰 변화만 감지 (0.3~0.4 권장)
    max_scenes: 반환할 최대 시점 수 — 슬라이드쇼 영상에서 수백 개 방지
    """
    ffmpeg_binary = resolve_ffmpeg_binary("ffmpeg")
    cmd = [
        ffmpeg_binary,
        "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr",
        "-an",
        "-f", "null", "-",
        "-loglevel", "info",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        timestamps: List[float] = []
        for line in result.stderr.splitlines():
            if "Parsed_showinfo" not in line:
                continue
            m = _SHOWINFO_PTS_RE.search(line)
            if m:
                timestamps.append(float(m.group(1)))
                if len(timestamps) >= max_scenes:
                    break
        return sorted(timestamps)
    except Exception as exc:
        print(f"[frame-extractor] scene detection failed: {exc}")
        return []


def _build_sample_timestamps(
    duration: float,
    interval_sec: int,
    max_frames: Optional[int],
    scene_timestamps: Optional[List[float]] = None,
) -> List[float]:
    if duration <= 0:
        return []

    interval = max(int(interval_sec), 1)
    regular = [float(t) for t in range(0, max(int(duration), 1), interval)]
    intro = [float(t) for t in range(0, min(90, int(duration)) + 1, 15)]
    outro_start = max(0, int(duration) - 90)
    outro = [float(t) for t in range(outro_start, int(duration), 15)]

    # 장면 전환 시점 주변 ±2s 를 추가 샘플링
    scene_zone: List[float] = []
    for t in (scene_timestamps or []):
        for offset in (-2.0, 0.0, 2.0, 4.0):
            scene_zone.append(t + offset)

    # intro → regular → scene_zone → outro 순으로 합산 후 정렬
    # int 기준 중복 제거로 float 오차 방지
    seen: set = set()
    all_timestamps: List[float] = []
    for t in sorted(intro + regular + scene_zone + outro):
        t = min(max(t, 0.0), max(duration - 1.0, 0.0))
        key = int(t)
        if key in seen:
            continue
        seen.add(key)
        all_timestamps.append(t)

    # max_frames 제한 시 균등 서브샘플링 (head 잘라내기 방지)
    if max_frames and len(all_timestamps) > max_frames:
        step = len(all_timestamps) / max_frames
        all_timestamps = [all_timestamps[int(i * step)] for i in range(max_frames)]

    return all_timestamps


def _extract_single_frame(video_path: str, output_path: str, timestamp: float) -> None:
    ffmpeg_binary = resolve_ffmpeg_binary("ffmpeg")
    cmd = [
        ffmpeg_binary,
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
    ffmpeg_binary = resolve_ffmpeg_binary("ffmpeg")
    cmd = [
        ffmpeg_binary,
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
    use_scene_detection: bool = True,
    scene_threshold: float = 0.35,
    max_scene_frames: int = 40,
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
        f" use_scene_detection={use_scene_detection}"
    )

    scene_timestamps: List[float] = []
    if use_scene_detection and duration > 0:
        print(f"[frame-extractor] scene detection start threshold={scene_threshold}")
        scene_timestamps = detect_scene_change_timestamps(
            video_path,
            threshold=scene_threshold,
            max_scenes=max_scene_frames,
        )
        print(f"[frame-extractor] scene detection end scenes={len(scene_timestamps)}")

    try:
        timestamps = _build_sample_timestamps(duration, interval_sec, max_frames, scene_timestamps)
        if timestamps:
            for index, timestamp in enumerate(timestamps, start=1):
                output_path = os.path.join(output_dir, f"frame_{index:04d}_{int(timestamp):06d}s.jpg")
                _extract_single_frame(video_path, output_path, timestamp)
        else:
            _extract_interval_frames(video_path, output_dir, interval_sec, max_frames)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        stderr = getattr(exc, "stderr", None)
        error_message = stderr.decode("utf-8", errors="ignore") if stderr else str(exc)
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
        f" scene_frames_added={len(scene_timestamps)}"
    )
    return frames
