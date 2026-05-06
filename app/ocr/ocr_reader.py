from __future__ import annotations

import base64
import mimetypes
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from app.config import OPENAI_API_KEY

VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
MAX_IMAGE_SIDE = int(os.getenv("OCR_VISION_MAX_IMAGE_SIDE", "1600"))
JPEG_QUALITY = int(os.getenv("OCR_VISION_JPEG_QUALITY", "85"))

OCR_VISION_PROMPT = """
You are reading a frame captured from a YouTube music playlist video.

Extract only text that is visibly present in the image and could be music information:
- artist names
- song titles
- timestamps
- track numbers
- track-list lines

Do not infer missing artist/title pairs.
Do not normalize or translate names.
Do not add explanations.
If there is no music-related text, return an empty string.
""".strip()

_client: Optional[Any] = None


def _get_client() -> Optional[Any]:
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _optimized_image_bytes(path: Path) -> tuple[bytes, str]:
    try:
        from PIL import Image
    except Exception:
        return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg"

    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        longest_side = max(width, height)
        if longest_side > MAX_IMAGE_SIDE:
            scale = MAX_IMAGE_SIDE / longest_side
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            image = image.resize(new_size)

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue(), "image/jpeg"


def _image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image_bytes, mime_type = _optimized_image_bytes(path)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def read_text_from_image(image_path: str, *, client: Optional[Any] = None, model: Optional[str] = None) -> str:
    openai_client = client or _get_client()
    if openai_client is None:
        return ""

    try:
        response = openai_client.responses.create(
            model=model or VISION_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": OCR_VISION_PROMPT},
                        {"type": "input_image", "image_url": _image_to_data_url(image_path)},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI vision OCR failed for {image_path}: {exc}") from exc

    return _extract_response_text(response)
