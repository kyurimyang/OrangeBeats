import base64
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_cookie_path() -> str:
    cookie_content = os.getenv("YTDLP_COOKIE_CONTENT", "").strip()
    cookie_file = os.getenv("YTDLP_COOKIE_FILE", "").strip()

    if cookie_content:
        tmp_path = Path("/tmp/yt_cookies.txt")
        try:
            decoded = base64.b64decode(cookie_content)
            tmp_path.write_bytes(decoded)
            logger.info("[ytdlp-opts] cookie loaded from YTDLP_COOKIE_CONTENT (%d bytes → %s)", len(decoded), tmp_path)
            return str(tmp_path)
        except Exception as e:
            logger.warning("[ytdlp-opts] YTDLP_COOKIE_CONTENT decode failed: %s", e)
            return ""

    if cookie_file:
        if Path(cookie_file).is_file():
            logger.info("[ytdlp-opts] cookie loaded from YTDLP_COOKIE_FILE: %s", cookie_file)
            return cookie_file
        logger.warning("[ytdlp-opts] YTDLP_COOKIE_FILE not found (skipping): %s", cookie_file)
        return ""

    logger.info("[ytdlp-opts] no cookie configured — using tv_embedded client only")
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
        logger.info("[ytdlp-opts] using PO token (visitor_data=%s)", "yes" if visitor_data else "no")
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
        logger.info("[ytdlp-opts] using proxy: %s...", proxy[:30])
    return opts
