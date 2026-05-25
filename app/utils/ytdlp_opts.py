import base64
import os
from pathlib import Path

_COOKIE_FILE = os.getenv("YTDLP_COOKIE_FILE", "").strip()
_COOKIE_CONTENT = os.getenv("YTDLP_COOKIE_CONTENT", "").strip()

_resolved_cookie_path: str = ""

if _COOKIE_CONTENT:
    _tmp_path = Path("/tmp/yt_cookies.txt")
    try:
        _tmp_path.write_bytes(base64.b64decode(_COOKIE_CONTENT))
        _resolved_cookie_path = str(_tmp_path)
    except Exception:
        pass
elif _COOKIE_FILE:
    _resolved_cookie_path = _COOKIE_FILE


def ytdlp_base_opts() -> dict:
    opts: dict = {"quiet": True, "no_warnings": True, "noplaylist": True}
    if _resolved_cookie_path:
        opts["cookiefile"] = _resolved_cookie_path
    return opts
