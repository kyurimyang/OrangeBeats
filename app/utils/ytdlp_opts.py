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
    # tv_embedded/android/ios: 서버 환경에서 안정적, web은 실제 브라우저 필요
    # 쿠키는 봇 감지 우회 목적으로만 사용 (클라이언트와 무관)
    path = _get_cookie_path()
    player_clients = ["tv_embedded", "android", "ios"]
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": player_clients}},
    }
    if path:
        opts["cookiefile"] = path
    return opts
