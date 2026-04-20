import secrets
from typing import Optional

from fastapi import Request, Response

from app.config import (
    SPOTIFY_SESSION_COOKIE_NAME,
    SPOTIFY_SESSION_COOKIE_SECURE,
    SPOTIFY_SESSION_MAX_AGE,
)


def get_session_id(request: Request) -> Optional[str]:
    session_id = (request.cookies.get(SPOTIFY_SESSION_COOKIE_NAME) or "").strip()
    return session_id or None


def get_or_create_session_id(request: Request, response: Response) -> str:
    existing = get_session_id(request)
    if existing:
        return existing

    session_id = secrets.token_urlsafe(32)
    response.set_cookie(
        key=SPOTIFY_SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=SPOTIFY_SESSION_COOKIE_SECURE,
        max_age=SPOTIFY_SESSION_MAX_AGE,
    )
    return session_id
