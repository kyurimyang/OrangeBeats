from pathlib import Path
import uuid


def download_youtube_audio(youtube_url: str, output_dir: Path) -> Path:
    try:
        import yt_dlp

        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(output_dir / f"{uuid.uuid4().hex}.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))
            if downloaded_path.exists():
                return downloaded_path

            matches = sorted(output_dir.glob(f"{downloaded_path.stem}.*"))
            if matches:
                return matches[0]

        raise FileNotFoundError("downloaded audio file not found")
    except Exception as exc:
        raise RuntimeError(f"youtube audio download failed: {exc}") from exc
