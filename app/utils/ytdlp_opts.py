import base64
import os
from pathlib import Path

_COOKIE_FILE = os.getenv("YTDLP_COOKIE_FILE", "").strip()
_COOKIE_CONTENT = os.getenv("YTDLP_COOKIE_CONTENT", "").strip()

_resolved_cookie_path: str = ""

if _COOKIE_CONTENT:
    _tmp_path = Path("/tmp/yt_cookies.txt")
    try:
        decoded = base64.b64decode(_COOKIE_CONTENT)
        _tmp_path.write_bytes(decoded)
        _resolved_cookie_path = str(_tmp_path)
        print(f"[ytdlp-opts] cookie loaded from YTDLP_COOKIE_CONTENT ({len(decoded)} bytes → {_tmp_path})")
    except Exception as e:
        print(f"[ytdlp-opts] YTDLP_COOKIE_CONTENT decode failed: {e}")
elif _COOKIE_FILE:
    _resolved_cookie_path = _COOKIE_FILE
    print(f"[ytdlp-opts] cookie loaded from YTDLP_COOKIE_FILE: {_COOKIE_FILE}")
else:
    print("[ytdlp-opts] no cookie configured (YTDLP_COOKIE_CONTENT and YTDLP_COOKIE_FILE both empty)")


def ytdlp_base_opts() -> dict:
    opts: dict = {"quiet": True, "no_warnings": True, "noplaylist": True}
    if _resolved_cookie_path:
        opts["cookiefile"] = _resolved_cookie_path
    return opts
