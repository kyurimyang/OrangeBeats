import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

from app.services.spotify_exceptions import SpotifyServiceError

DEFAULT_TIMEOUT = 20
_TRANSIENT_STATUS_CODES = {502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 0.5
_RATE_LIMIT_FILE = Path(__file__).resolve().parents[2] / ".spotify_rate_limit.json"
_rate_limited_until = 0.0
_rate_limit_message: Optional[str] = None

# Minimum interval between Spotify API calls (seconds). Prevents burst spikes.
_MIN_REQUEST_INTERVAL = 0.05
_last_request_time = 0.0
_throttle_lock = threading.Lock()


def _load_rate_limit_state() -> None:
    global _rate_limited_until
    global _rate_limit_message

    if not _RATE_LIMIT_FILE.exists():
        _rate_limited_until = 0.0
        _rate_limit_message = None
        return

    try:
        data = json.loads(_RATE_LIMIT_FILE.read_text(encoding="utf-8"))
        _rate_limited_until = float(data.get("rate_limited_until") or 0.0)
        message = (data.get("message") or "").strip()
        _rate_limit_message = message or None
    except Exception:
        _rate_limited_until = 0.0
        _rate_limit_message = None


def _save_rate_limit_state(retry_after: int) -> None:
    global _rate_limited_until
    global _rate_limit_message

    retry_after = max(1, int(retry_after or 60))
    _rate_limited_until = time.time() + retry_after
    _rate_limit_message = (
        f"Spotify API rate limit active: 429 / Too many requests (retry_after={retry_after})"
    )

    try:
        _RATE_LIMIT_FILE.write_text(
            json.dumps(
                {
                    "rate_limited_until": _rate_limited_until,
                    "retry_after": retry_after,
                    "message": _rate_limit_message,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _clear_rate_limit_state_if_expired() -> None:
    global _rate_limited_until
    global _rate_limit_message

    if not _rate_limited_until or time.time() < _rate_limited_until:
        return

    _rate_limited_until = 0.0
    _rate_limit_message = None
    try:
        _RATE_LIMIT_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _raise_if_rate_limited() -> None:
    _clear_rate_limit_state_if_expired()
    if not _rate_limited_until:
        return

    retry_after = max(1, int(_rate_limited_until - time.time()))
    message = _rate_limit_message or "Spotify API rate limit active: 429 / Too many requests"
    if "retry_after=" in message:
        message = message.split(" (retry_after=", 1)[0]
    raise SpotifyServiceError(f"{message} (retry_after={retry_after})")


def _auth_headers(access_token: str, content_type: str = "application/json") -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _throttle() -> None:
    global _last_request_time
    with _throttle_lock:
        now = time.time()
        wait = _MIN_REQUEST_INTERVAL - (now - _last_request_time)
        _last_request_time = now + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def spotify_request(
    method: str,
    url: str,
    *,
    access_token: Optional[str] = None,
    params: Optional[Dict] = None,
    json: Optional[Dict] = None,
    data=None,
    content_type: str = "application/json",
    timeout: int = DEFAULT_TIMEOUT,
):
    if not access_token:
        raise SpotifyServiceError("Spotify access token이 없습니다.")

    _raise_if_rate_limited()
    _throttle()

    headers = _auth_headers(access_token, content_type=content_type)
    last_exc: Optional[Exception] = None
    response = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.3)
                logger.warning("[spotify] request error on attempt %d, retrying in %.1fs: %s", attempt + 1, wait, exc)
                time.sleep(wait)
                continue
            raise SpotifyServiceError(f"Spotify 요청 실패: {str(exc)}") from exc

        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            try:
                retry_after = max(1, int(retry_after_header or "60"))
            except ValueError:
                retry_after = 60
            _save_rate_limit_state(retry_after)
            raise SpotifyServiceError(_rate_limit_message or f"Spotify API rate limit active: 429 / Too many requests (retry_after={retry_after})")

        if response.status_code in _TRANSIENT_STATUS_CODES and attempt < _MAX_RETRIES:
            wait = _RETRY_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.3)
            logger.warning("[spotify] %d on attempt %d, retrying in %.1fs", response.status_code, attempt + 1, wait)
            time.sleep(wait)
            continue

        return response

    # 모든 재시도 소진 — 마지막 응답 반환 (호출부에서 상태코드 처리)
    if response is not None:
        return response
    raise SpotifyServiceError(f"Spotify 요청 실패: {str(last_exc)}")


_load_rate_limit_state()
