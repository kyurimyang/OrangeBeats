import secrets
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import FRONTEND_URL
from app.services.spotify_service import (
    SpotifyServiceError,
    create_playlist_from_songs,
    exchange_code_for_token,
    get_spotify_login_url,
)
from app.services.spotify_session import (
    ensure_valid_access_token,
    is_logged_in,
    save_token_data,
    spotify_auth_state_store,
)

router = APIRouter(prefix='/spotify', tags=['Spotify'])


def _spotify_http_status(exc: SpotifyServiceError) -> int:
    message = str(exc)
    if '429' in message or 'Too many requests' in message or 'rate limit' in message.lower():
        return 429
    return 500


@router.get('/login')
def spotify_login():
    state = secrets.token_urlsafe(16)
    spotify_auth_state_store[state] = True

    login_url = get_spotify_login_url(state=state)

    print('=== /spotify/login called ===')
    print('generated state =', state)
    print('login_url =', login_url)

    return {
        'login_url': login_url,
        'state': state,
    }


@router.get('/callback')
def spotify_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    print('=== /spotify/callback called ===')
    print('callback state =', state)

    if state not in spotify_auth_state_store:
        print('invalid state')
        return RedirectResponse(
            url=f'{FRONTEND_URL}?spotify_login=failed&reason=invalid_state',
            status_code=302,
        )

    try:
        token_data = exchange_code_for_token(code)
        print('granted scope =', token_data.get('scope'))
        save_token_data(token_data)

        spotify_auth_state_store.pop(state, None)

        return RedirectResponse(
            url=f'{FRONTEND_URL}?spotify_login=success',
            status_code=302,
        )

    except SpotifyServiceError as e:
        print('SpotifyServiceError =', str(e))
        return RedirectResponse(
            url=f'{FRONTEND_URL}?spotify_login=failed&reason=spotify_service_error',
            status_code=302,
        )

    except Exception as e:
        print('Unexpected callback error =', str(e))
        return RedirectResponse(
            url=f'{FRONTEND_URL}?spotify_login=failed&reason=unknown_error',
            status_code=302,
        )


@router.get('/login-status')
def spotify_login_status():
    try:
        token = ensure_valid_access_token()
        return {
            'logged_in': bool(token),
        }
    except Exception:
        return {
            'logged_in': is_logged_in(),
        }


@router.post('/create-playlist')
def create_spotify_playlist(payload: Dict):
    try:
        access_token = ensure_valid_access_token()
    except SpotifyServiceError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    print('=== /spotify/create-playlist called ===')
    print('payload =', payload)
    print('token exists =', bool(access_token))

    playlist_name = (payload.get('playlist_name') or '새 플레이리스트').strip()
    songs: List[Dict[str, str]] = payload.get('songs', [])

    print('playlist_name =', playlist_name)
    print('songs count =', len(songs))
    print('songs sample =', songs[:3])

    if not songs:
        raise HTTPException(status_code=400, detail='songs가 비어 있습니다.')

    try:
        result = create_playlist_from_songs(
            access_token=access_token,
            playlist_name=playlist_name,
            songs=songs,
            playlist_description='Created from YouTube playlist text',
            public=True,
        )

        return {
            'success': True,
            'result': result,
        }

    except SpotifyServiceError as e:
        print('SpotifyServiceError =', str(e))
        raise HTTPException(status_code=_spotify_http_status(e), detail=str(e))
