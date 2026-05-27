import base64
import os
from functools import lru_cache
from pathlib import Path


def _resolve_cookie_path() -> str:
    cookie_content = os.getenv("YTDLP_COOKIE_CONTENT", "").strip()
    cookie_file = os.getenv("YTDLP_COOKIE_FILE", "").strip()

    if cookie_content:
        tmp_path = Path("/tmp/yt_cookies.txt")
        try:
            decoded = base64.b64decode(cookie_content)
            tmp_path.write_bytes(decoded)
            print(f"[ytdlp-opts] cookie loaded from YTDLP_COOKIE_CONTENT ({len(decoded)} bytes → {tmp_path})")
            return str(tmp_path)
        except Exception as e:
            print(f"[ytdlp-opts] YTDLP_COOKIE_CONTENT decode failed: {e}")
            return ""

    if cookie_file:
        if Path(cookie_file).is_file():
            print(f"[ytdlp-opts] cookie loaded from YTDLP_COOKIE_FILE: {cookie_file}")
            return cookie_file
        print(f"[ytdlp-opts] YTDLP_COOKIE_FILE not found (skipping): {cookie_file}")
        return ""

    print("[ytdlp-opts] no cookie configured — using tv_embedded client only")
    return ""


@lru_cache(maxsize=1)
def _get_cookie_path() -> str:
    return _resolve_cookie_path()


def ytdlp_base_opts() -> dict:
    # ios → tv_embedded 순: 서버 환경에서 ios가 가장 안정적
    # check_formats=False: 데이터센터 IP에서 CDN HEAD 요청이 차단될 때 우회
    path = _get_cookie_path()
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "check_formats": False,
        "extractor_args": {"youtube": {"player_client": ["ios", "tv_embedded", "android"]}},
    }
    if path:
        opts["cookiefile"] = path
    return opts
