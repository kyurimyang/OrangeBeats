import os
import uuid
from pathlib import Path

_YTDLP_COOKIE_FILE = os.getenv("YTDLP_COOKIE_FILE", "").strip()


def _ytdlp_base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    if _YTDLP_COOKIE_FILE:
        opts["cookiefile"] = _YTDLP_COOKIE_FILE
    return opts


def download_youtube_video(
    url: str,
    output_dir: str = "./tmp/downloads",
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    unique_id = uuid.uuid4().hex
    output_template = os.path.join(output_dir, f"{unique_id}.%(ext)s")

    ydl_opts = {
        **_ytdlp_base_opts(),
        "format": "mp4/bestvideo+bestaudio/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
    }

    try:
        import yt_dlp

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)

            base, ext = os.path.splitext(downloaded_path)
            if ext.lower() != ".mp4":
                mp4_path = base + ".mp4"
                if os.path.exists(mp4_path):
                    downloaded_path = mp4_path

            if not os.path.exists(downloaded_path):
                raise FileNotFoundError("다운로드된 영상 파일을 찾을 수 없습니다.")

            return downloaded_path

    except Exception as e:
        raise RuntimeError(f"유튜브 영상 다운로드 실패: {str(e)}") from e