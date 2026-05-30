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
    path = _get_cookie_path()
    po_token = os.getenv("YTDLP_PO_TOKEN", "").strip()
    visitor_data = os.getenv("YTDLP_VISITOR_DATA", "").strip()

    if po_token:
        # PO token 있음: web 클라이언트 + 토큰으로 데이터센터 IP 우회
        yt_args: dict = {
            "player_client": ["web"],
            "po_token": [f"web+{po_token}"],
        }
        if visitor_data:
            yt_args["visitor_data"] = [visitor_data]
        print(f"[ytdlp-opts] using PO token (visitor_data={'yes' if visitor_data else 'no'})")
    else:
        # PO token 없음: 모바일 클라이언트 fallback
        yt_args = {"player_client": ["ios", "tv_embedded", "android"]}

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "check_formats": False,
        "extractor_args": {"youtube": yt_args},
    }
    if path:
        opts["cookiefile"] = path
    proxy = os.getenv("YTDLP_PROXY", "").strip()
    if proxy:
        opts["proxy"] = proxy
        print(f"[ytdlp-opts] using proxy: {proxy[:30]}...")
    return opts
