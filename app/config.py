import os
import re
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()

_PRIVATE_FRONTEND_ORIGIN_RE = re.compile(
    r"^https?://(?:"
    r"localhost|"
    r"127(?:\.\d{1,3}){3}|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
    r")(?::\d+)?$",
    re.IGNORECASE,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
FRONTEND_ALLOWED_ORIGINS = os.getenv("FRONTEND_ALLOWED_ORIGINS", "")
SPOTIFY_SESSION_COOKIE_NAME = os.getenv("SPOTIFY_SESSION_COOKIE_NAME", "ob_session")
SPOTIFY_SESSION_MAX_AGE = int(os.getenv("SPOTIFY_SESSION_MAX_AGE", "2592000"))
SPOTIFY_SESSION_COOKIE_SECURE = os.getenv("SPOTIFY_SESSION_COOKIE_SECURE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ACRCLOUD_HOST = os.getenv("ACRCLOUD_HOST", "").strip()
ACRCLOUD_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY", "").strip()
ACRCLOUD_ACCESS_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET", "").strip()
ADMIN_KEY = os.getenv("ADMIN_KEY", "").strip()


def _normalize_origin(origin: str | None) -> str:
    if not origin:
        return ""

    parts = urlsplit(origin.strip())
    if not parts.scheme or not parts.netloc:
        return ""

    return f"{parts.scheme}://{parts.netloc}"


def normalize_frontend_url(frontend_url: str | None) -> str:
    if not frontend_url:
        return ""

    parts = urlsplit(frontend_url.strip())
    if not parts.scheme or not parts.netloc:
        return ""

    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment)).rstrip("/")


def get_allowed_frontend_origins() -> set[str]:
    allowed: set[str] = set()

    for raw_origin in FRONTEND_ALLOWED_ORIGINS.split(","):
        normalized = _normalize_origin(raw_origin)
        if normalized:
            allowed.add(normalized)

    frontend_origin = _normalize_origin(FRONTEND_URL)
    if frontend_origin:
        allowed.add(frontend_origin)

    return allowed


def is_allowed_frontend_url(frontend_url: str | None) -> bool:
    normalized_origin = _normalize_origin(frontend_url)
    if not normalized_origin:
        return False

    if normalized_origin in get_allowed_frontend_origins():
        return True

    return bool(_PRIVATE_FRONTEND_ORIGIN_RE.match(normalized_origin))
