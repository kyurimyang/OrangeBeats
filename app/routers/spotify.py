import secrets
import time
from typing import Annotated, Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.config import (
    FRONTEND_URL,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SESSION_MAX_AGE,
    SPOTIFY_SESSION_COOKIE_NAME,
    SPOTIFY_SESSION_COOKIE_SECURE,
    is_allowed_frontend_url,
    normalize_frontend_url,
)
from app.dependencies.spotify_session import get_spotify_session_service
from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
    exchange_code_for_token,
    get_spotify_login_url,
)
from app.services.spotify_playlist import analyze_spotify_candidates
from app.services.spotify_session_service import SpotifySessionService
from app.sessions.session_id import get_or_create_session_id, get_session_id

router = APIRouter(prefix="/spotify", tags=["Spotify"])
SpotifySessionDep = Annotated[SpotifySessionService, Depends(get_spotify_session_service)]


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
    configured = normalize_frontend_url(SPOTIFY_REDIRECT_URI)
    if configured:
        return configured
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
def spotify_login(
    request: Request,
    response: Response,
    session_service: SpotifySessionDep,
    frontend_origin: str | None = Query(default=None),
):
    session_id = get_or_create_session_id(request, response)
    state = secrets.token_urlsafe(16)
    redirect_origin = _resolve_frontend_origin(frontend_origin)
    callback_redirect_uri = _resolve_callback_redirect_uri(request)
    session_service.save_auth_state(
        state=state,
        session_id=session_id,
        frontend_origin=redirect_origin,
        redirect_uri=callback_redirect_uri,
    )

    login_url = get_spotify_login_url(state=state, redirect_uri=callback_redirect_uri)

    print("=== /spotify/login called ===")
    print("session_id =", session_id)
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
    session_service: SpotifySessionDep,
    state: str = Query(...),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    print("=== /spotify/callback called ===")
    print("callback state =", state)

    auth_state = session_service.pop_auth_state(state)
    frontend_redirect = _resolve_frontend_origin(auth_state.frontend_origin if auth_state else None)
    callback_redirect_uri = auth_state.redirect_uri if auth_state else None

    if not auth_state:
        print("invalid state")
        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "failed", "invalid_state"),
            status_code=302,
        )

    if error or not code:
        print("spotify auth error =", error)
        return RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "failed", error or "no_code"),
            status_code=302,
        )

    try:
        token_data = exchange_code_for_token(code, redirect_uri=callback_redirect_uri)
        print("granted scope =", token_data.get("scope"))
        session_service.save_token_data(auth_state.session_id, token_data)

        response = RedirectResponse(
            url=_build_frontend_redirect(frontend_redirect, "success"),
            status_code=302,
        )
        # Ensure browser has the same session id used for saved tokens.
        response.set_cookie(
            key=SPOTIFY_SESSION_COOKIE_NAME,
            value=auth_state.session_id,
            httponly=True,
            samesite="lax",
            secure=SPOTIFY_SESSION_COOKIE_SECURE,
            max_age=SPOTIFY_SESSION_MAX_AGE,
        )
        return response

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
def spotify_login_status(
    request: Request,
    session_service: SpotifySessionDep,
):
    session_id = get_session_id(request)
    if not session_id:
        return {
            "logged_in": False,
            "reason": "missing_session",
        }

    try:
        token = session_service.ensure_valid_access_token(session_id)
        return {
            "logged_in": bool(token),
        }
    except SpotifyServiceError as exc:
        if "invalid_grant" in str(exc).lower():
            session_service.clear_tokens(session_id)
        return {
            "logged_in": False,
            "reason": str(exc),
        }
    except Exception as exc:
        return {
            "logged_in": False,
            "reason": str(exc),
        }


@router.post("/logout")
def spotify_logout(
    request: Request,
    response: Response,
    session_service: SpotifySessionDep,
):
    session_id = get_session_id(request)
    if session_id:
        session_service.clear_tokens(session_id)

    response.delete_cookie(
        key=SPOTIFY_SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=SPOTIFY_SESSION_COOKIE_SECURE,
    )
    return {
        "success": True,
        "logged_in": False,
    }


@router.post("/create-playlist")
def create_spotify_playlist(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    session_id = get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Spotify 로그인 세션이 없습니다.")

    try:
        access_token = session_service.ensure_valid_access_token(session_id)
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


@router.post("/match-candidates")
def match_spotify_candidates(
    payload: Dict,
    request: Request,
    session_service: SpotifySessionDep,
):
    session_id = get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Spotify 로그인이 필요합니다.")

    songs: List[Dict[str, str]] = payload.get("songs", []) or payload.get("extracted_songs", [])
    if not songs:
        raise HTTPException(status_code=400, detail="매칭할 곡 목록이 없습니다.")

    try:
        access_token = session_service.ensure_valid_access_token(session_id)
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    started_at = time.perf_counter()
    try:
        results = analyze_spotify_candidates(
            access_token=access_token,
            songs=songs,
            market=str(payload.get("market") or "KR"),
            source_mode=str(payload.get("source_mode") or payload.get("mode") or "text"),
        )
    except SpotifyServiceError as exc:
        raise HTTPException(status_code=_spotify_http_status(exc), detail=str(exc)) from exc

    spotify_elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    candidate_count = sum(1 for item in results if item.get("matched") and item.get("spotify_uri"))
    needs_review_count = sum(1 for item in results if item.get("confidence_label") in {"mid", "low"})
    failed_count = sum(1 for item in results if item.get("confidence_label") == "failed")
    matched_tracks = [item for item in results if item.get("matched") and item.get("spotify_uri")]
    unmatched_tracks = [item for item in results if not (item.get("matched") and item.get("spotify_uri"))]

    return {
        "success": True,
        "analysis_state": "candidates_ready",
        "needs_fallback": False,
        "next_action": "select_tracks",
        "message": "Spotify 후보 검색을 완료했습니다.",
        "songs": songs,
        "extracted_songs": songs,
        "results": results,
        "matched_tracks": matched_tracks,
        "unmatched_tracks": unmatched_tracks,
        "extracted_count": len(songs),
        "spotify_candidate_count": candidate_count,
        "candidate_count": candidate_count,
        "needs_review_count": needs_review_count,
        "failed_count": failed_count,
        "spotify_elapsed_ms": spotify_elapsed_ms,
        "timings": {"spotify_elapsed_ms": spotify_elapsed_ms},
    }
