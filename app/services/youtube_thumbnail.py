import base64
import re
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

from app.config import YOUTUBE_API_KEY


class YouTubeThumbnailError(Exception):
    pass


def extract_video_id(youtube_url: str) -> str:
    url = (youtube_url or "").strip()

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise YouTubeThumbnailError("유효한 YouTube video id를 추출하지 못했습니다.")


def get_youtube_thumbnail_url(video_id: str) -> str:
    api_key = YOUTUBE_API_KEY
    if not api_key:
        raise YouTubeThumbnailError("YOUTUBE_API_KEY가 설정되어 있지 않습니다.")

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "id": video_id,
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=15)
    if response.status_code != 200:
        raise YouTubeThumbnailError(
            f"YouTube 썸네일 조회 실패: {response.status_code} / {response.text}"
        )

    data = response.json()
    items = data.get("items", [])
    if not items:
        raise YouTubeThumbnailError("해당 video id의 YouTube 영상을 찾지 못했습니다.")

    thumbnails = items[0].get("snippet", {}).get("thumbnails", {})
    for key in ["maxres", "standard", "high", "medium", "default"]:
        if key in thumbnails and thumbnails[key].get("url"):
            return thumbnails[key]["url"]

    raise YouTubeThumbnailError("사용 가능한 YouTube 썸네일 URL을 찾지 못했습니다.")


def _download_image(url: str) -> bytes:
    response = requests.get(url, timeout=20)
    if response.status_code != 200:
        raise YouTubeThumbnailError(
            f"썸네일 이미지 다운로드 실패: {response.status_code} / {response.text}"
        )
    return response.content


def _compress_to_spotify_jpeg(image_bytes: bytes, max_bytes: int = 256 * 1024) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    width, height = image.size
    quality = 90

    while True:
        buffer = BytesIO()
        resized = image.resize((width, height))
        resized.save(buffer, format="JPEG", quality=quality, optimize=True)
        result = buffer.getvalue()

        if len(result) <= max_bytes:
            return result

        if quality > 50:
            quality -= 10
        else:
            width = int(width * 0.9)
            height = int(height * 0.9)

        if width < 200 or height < 200:
            raise YouTubeThumbnailError("이미지를 Spotify 업로드 크기 제한(256KB) 이하로 줄이지 못했습니다.")


def get_thumbnail_base64_from_youtube_url(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)
    thumbnail_url = get_youtube_thumbnail_url(video_id)
    image_bytes = _download_image(thumbnail_url)
    jpeg_bytes = _compress_to_spotify_jpeg(image_bytes)
    return base64.b64encode(jpeg_bytes).decode("utf-8")