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
    print("[ytdlp-opts] no cookie configured — using tv_embedded client only")


def ytdlp_base_opts() -> dict:
    # tv_embedded: YouTube TV 클라이언트. 데이터센터 IP에서도 쿠키 없이 동작하는 경우 많음.
    # web: 일반 웹 클라이언트 (fallback). 쿠키가 있으면 bot 우회에 도움.
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "tv_embedded"]}},
    }
    if _resolved_cookie_path:
        opts["cookiefile"] = _resolved_cookie_path
    return opts
