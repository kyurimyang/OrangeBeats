from typing import Any, Dict, List

from app.services.spotify_api import add_tracks_to_playlist, create_playlist
from app.services.spotify_common import _is_suspicious_song
from app.services.spotify_exceptions import SpotifyServiceError
from app.services.spotify_matching import pick_best_track_match


def create_playlist_from_songs(
    access_token: str,
    playlist_name: str,
    songs: List[Dict[str, str]],
    playlist_description: str = "",
    public: bool = True,
) -> Dict[str, Any]:
    if not songs:
        raise SpotifyServiceError("생성할 곡 목록이 없습니다.")

    playlist = create_playlist(
        access_token=access_token,
        name=playlist_name,
        description=playlist_description,
        public=public,
    )

    matched_uris: List[str] = []
    matched_debug: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_uris = set()

    for song in songs:
        title = (song.get("title") or "").strip()
        artist = (song.get("artist") or "").strip() or None

        if not title:
            unmatched.append({"song": song, "reason": "title 없음"})
            continue

        if _is_suspicious_song(song):
            unmatched.append({"song": song, "reason": "artist/title 동일 또는 정보 부족"})
            continue

        match = pick_best_track_match(
            access_token=access_token,
            title=title,
            artist=artist,
            market=None,
        )

        if match:
            if match["uri"] not in seen_uris:
                seen_uris.add(match["uri"])
                matched_uris.append(match["uri"])

            matched_debug.append({
                "input": {
                    "artist": artist or "",
                    "title": title,
                },
                "matched_name": match["name"],
                "matched_artists": match["artists"],
                "score": match["score"],
                "orientation": match.get("orientation", "original"),
                "llm_reranked": match.get("llm_reranked", False),
                "llm_confidence": match.get("llm_confidence", ""),
                "llm_reason": match.get("llm_reason", ""),
                "search_title": match.get("search_title", ""),
                "search_artist": match.get("search_artist", ""),
                "top_candidates": [
                    {
                        "name": candidate["name"],
                        "artists": candidate["artists"],
                        "score": candidate["score"],
                        "orientation": candidate["orientation"],
                    }
                    for candidate in match.get("top_candidates", [])
                ],
            })
        else:
            unmatched.append({
                "song": song,
                "reason": "spotify 검색 실패 또는 저신뢰 매칭",
            })

    if matched_uris:
        add_tracks_to_playlist(
            access_token=access_token,
            playlist_id=playlist["id"],
            track_uris=matched_uris,
        )

    return {
        "playlist_id": playlist["id"],
        "playlist_url": playlist["external_urls"]["spotify"],
        "matched_count": len(matched_uris),
        "unmatched_count": len(unmatched),
        "matched": matched_debug,
        "unmatched": unmatched,
    }