from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.services.spotify_api import search_track
from app.services.spotify_common import (
    _artist_variants,
    _clean_track_title_for_search,
    _normalize_text,
)


def _candidate_score(candidate: Dict[str, Any], title: str, artist: Optional[str]) -> float:
    target_title = _normalize_text(title)
    target_title_clean = _normalize_text(_clean_track_title_for_search(title))
    target_artist = _normalize_text(artist or "")

    cand_title_raw = candidate.get("name", "")
    cand_title = _normalize_text(cand_title_raw)
    cand_title_clean = _normalize_text(_clean_track_title_for_search(cand_title_raw))

    cand_artists = " ".join(a.get("name", "") for a in candidate.get("artists", []))
    cand_artist_norm = _normalize_text(cand_artists)

    title_score_raw = (
        SequenceMatcher(None, target_title, cand_title).ratio()
        if target_title and cand_title
        else 0.0
    )
    title_score_clean = (
        SequenceMatcher(None, target_title_clean, cand_title_clean).ratio()
        if target_title_clean and cand_title_clean
        else 0.0
    )
    title_score = max(title_score_raw, title_score_clean)

    artist_score = 0.0
    if target_artist and cand_artist_norm:
        artist_score = SequenceMatcher(None, target_artist, cand_artist_norm).ratio()

    score = title_score * 0.8 + artist_score * 0.2

    if target_title_clean and target_title_clean == cand_title_clean:
        score += 0.12

    if target_artist and target_artist in cand_artist_norm:
        score += 0.08

    bad_tokens = ["instrumental", "remix", "live", "sped up", "slowed"]
    if any(token in cand_title for token in bad_tokens):
        score -= 0.06

    return round(score, 4)


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    seen_ids = set()
    ranked: List[Dict[str, Any]] = []

    raw_title = (title or "").strip()
    clean_title = _clean_track_title_for_search(raw_title)

    title_variants = []
    for t in [raw_title, clean_title]:
        if t and t not in title_variants:
            title_variants.append(t)

    artist_variants = _artist_variants(artist)
    search_cases = []

    # 1) title + artist
    for t in title_variants:
        for a in artist_variants:
            if t and a:
                search_cases.append((t, a))

    # 2) title only
    for t in title_variants:
        if t:
            search_cases.append((t, None))

    dedup_cases = []
    seen_cases = set()
    for case in search_cases:
        if case not in seen_cases:
            seen_cases.add(case)
            dedup_cases.append(case)

    for search_title, search_artist in dedup_cases:
        candidates = search_track(
            access_token=access_token,
            title=search_title,
            artist=search_artist,
            market=market,
            limit=10,
        )

        for candidate in candidates:
            candidate_id = candidate.get("id")
            if not candidate_id or candidate_id in seen_ids:
                continue

            seen_ids.add(candidate_id)
            ranked.append({
                "uri": candidate["uri"],
                "name": candidate.get("name", ""),
                "artists": [a.get("name", "") for a in candidate.get("artists", [])],
                "score": _candidate_score(candidate, title=raw_title, artist=artist),
                "search_title": search_title,
                "search_artist": search_artist or "",
            })

    if not ranked:
        return None

    ranked.sort(key=lambda x: x["score"], reverse=True)
    best = ranked[0]

    if best["score"] < 0.66:
        return None

    return best