import secrets
from typing import Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.config import FRONTEND_URL, is_allowed_frontend_url, normalize_frontend_url
from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
    exchange_code_for_token,
    get_spotify_login_url,
)
from app.services.spotify_session import (
    clear_tokens,
    ensure_valid_access_token,
    pop_auth_state,
    save_auth_state,
    save_token_data,
)

router = APIRouter(prefix="/spotify", tags=["Spotify"])


def _spotify_http_status(exc: SpotifyServiceError) -> int:
    message = str(exc)
    if "429" in message or "Too many requests" in message or "rate limit" in message.lower():
        return 429
    return 500


def _resolve_frontend_origin(frontend_origin: str | None) -> str:
    if is_allowed_frontend_url(frontend_origin):
        normalized = normalize_frontend_url(frontend_origin)
        if normalized:
            return normalized

    return normalize_frontend_url(FRONTEND_URL) or FRONTEND_URL.rstrip("/")


def _resolve_callback_redirect_uri(request: Request) -> str:
    return str(request.url_for("spotify_callback"))


def _build_frontend_redirect(base_url: str, status: str, reason: str | None = None) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["spotify_login"] = status

    if reason is not None:
        query["reason"] = reason
    else:
        query.pop("reason", None)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@router.get("/login")
def spotify_login(request: Request, frontend_origin: str | None = Query(default=None)):
    state = secrets.token_urlsafe(16)
    redirect_origin = _resolve_frontend_origin(frontend_origin)
    callback_redirect_uri = _resolve_callback_redirect_uri(request)
    save_auth_state(state, redirect_origin, callback_redirect_uri)

    login_url = get_spotify_login_url(state=state, redirect_uri=callback_redirect_uri)

    print("=== /spotify/login called ===")
    print("generated state =", state)
    print("frontend_origin =", redirect_origin)
    print("callback_redirect_uri =", callback_redirect_uri)
    print("login_url =", login_url)

    return {
        "login_url": login_url,
        "state": state,
    }


@router.get("/callback")
def spotify_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    print("=== /spotify/callback called ===")
    print("callback state =", state)

    auth_state = pop_auth_state(state)
    frontend_redirect = _resolve_frontend_origin(auth_state.get("frontend_origin") if auth_state else None)
    callback_redirect_uri = auth_state.get("redirect_uri") if auth_state else None

    if not auth_state:
        print("invalid state")
        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "failed", "invalid_state"),
            status_code=302,
        )

    try:
        token_data = exchange_code_for_token(code, redirect_uri=callback_redirect_uri)
        print("granted scope =", token_data.get("scope"))
        save_token_data(token_data)

        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "success"),
            status_code=302,
        )

    except SpotifyServiceError as exc:
        print("SpotifyServiceError =", str(exc))
        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "failed", "spotify_service_error"),
            status_code=302,
        )

    except Exception as exc:
        print("Unexpected callback error =", str(exc))
        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "failed", "unknown_error"),
            status_code=302,
        )


@router.get("/login-status")
def spotify_login_status():
    try:
        token = ensure_valid_access_token()
        return {
            "logged_in": bool(token),
        }
    except SpotifyServiceError as exc:
        if "invalid_grant" in str(exc).lower():
            clear_tokens()
        return {
            "logged_in": False,
            "reason": str(exc),
        }
    except Exception as exc:
        return {
            "logged_in": False,
            "reason": str(exc),
        }


@router.post("/create-playlist")
def create_spotify_playlist(payload: Dict):
    try:
        access_token = ensure_valid_access_token()
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    print("=== /spotify/create-playlist called ===")
    print("payload =", payload)
    print("token exists =", bool(access_token))

    playlist_name = (payload.get("playlist_name") or "Spotify Playlist").strip()
    songs: List[Dict[str, str]] = payload.get("songs", [])

    print("playlist_name =", playlist_name)
    print("songs count =", len(songs))
    print("songs sample =", songs[:3])

    if not songs:
        raise HTTPException(status_code=400, detail="songs가 비어 있습니다.")

    try:
        result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=playlist_name,
            songs=songs,
            playlist_description="Created from YouTube playlist text",
            public=True,
        )

        return {
            "success": True,
            "result": result,
        }

    except SpotifyServiceError as exc:
        print("SpotifyServiceError =", str(exc))
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc))
