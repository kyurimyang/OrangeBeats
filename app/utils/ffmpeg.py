import os
import shutil


def resolve_ffmpeg_binary(binary_name: str) -> str:
    env_key = "FFPROBE_BINARY" if binary_name == "ffprobe" else "FFMPEG_BINARY"
    configured = (os.getenv(env_key) or "").strip()
    if configured:
        return configured

    resolved = shutil.which(binary_name)
    if resolved:
        return resolved

    raise RuntimeError(
        f"{binary_name} executable not found. Install ffmpeg and add it to PATH, "
        f"or set {env_key} to the executable path."
    )
