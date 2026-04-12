from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.clients.openai_client import rerank_spotify_candidates_with_llm
from app.services.spotify_api import search_track
from app.services.spotify_common import (
    _artist_variants,
    _clean_track_title_for_search,
    _normalize_text,
    _token_overlap_ratio,
)


def _safe_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _title_score(input_title: str, candidate_title: str) -> float:
    input_title_raw = _normalize_text(input_title)
    input_title_clean = _normalize_text(_clean_track_title_for_search(input_title))

    cand_title_raw = _normalize_text(candidate_title)
    cand_title_clean = _normalize_text(_clean_track_title_for_search(candidate_title))

    raw_ratio = _safe_ratio(input_title_raw, cand_title_raw)
    clean_ratio = _safe_ratio(input_title_clean, cand_title_clean)
    token_ratio = _token_overlap_ratio(input_title_clean, cand_title_clean)

    score = max(raw_ratio, clean_ratio) * 0.75 + token_ratio * 0.25

    if input_title_clean and cand_title_clean and input_title_clean == cand_title_clean:
        score += 0.10

    return round(min(score, 1.0), 4)


def _artist_score(input_artist: Optional[str], candidate_artists: List[str]) -> float:
    if not input_artist:
        return 0.0

    target_variants = _artist_variants(input_artist)
    candidate_joined = " ".join(candidate_artists)
    candidate_norm = _normalize_text(candidate_joined)

    best = 0.0
    for variant in target_variants:
        variant_norm = _normalize_text(variant or "")
        if not variant_norm or not candidate_norm:
            continue

        ratio = _safe_ratio(variant_norm, candidate_norm)
        token_ratio = _token_overlap_ratio(variant_norm, candidate_norm)
        score = ratio * 0.7 + token_ratio * 0.3
        best = max(best, score)

        if variant_norm and variant_norm in candidate_norm:
            best = max(best, min(score + 0.08, 1.0))

    return round(min(best, 1.0), 4)


def _orientation_conflict_penalty(
    input_title: str,
    input_artist: Optional[str],
    candidate_title: str,
    candidate_artists: List[str],
) -> float:
    """
    입력이 뒤집힌 것 같은 경우를 감지하기 위한 패널티/보너스 계산용.
    candidate_title이 오히려 input_artist와 더 비슷하고,
    candidate_artists가 input_title과 더 비슷하면 원본 방향엔 불리하게 작용.
    """
    if not input_artist:
        return 0.0

    cand_artist_joined = " ".join(candidate_artists)

    title_vs_title = _title_score(input_title, candidate_title)
    artist_vs_artist = _artist_score(input_artist, candidate_artists)

    swapped_title_like = _title_score(input_artist, candidate_title)
    swapped_artist_like = _artist_score(input_title, candidate_artists)

    original_total = title_vs_title + artist_vs_artist
    swapped_like_total = swapped_title_like + swapped_artist_like

    if swapped_like_total > original_total + 0.20:
        return 0.10

    return 0.0


def _candidate_score(
    candidate: Dict[str, Any],
    title: str,
    artist: Optional[str],
    orientation: str,
) -> float:
    cand_title = candidate.get("name", "")
    cand_artists = [a.get("name", "") for a in candidate.get("artists", [])]

    title_score = _title_score(title, cand_title)
    artist_score = _artist_score(artist, cand_artists)

    score = title_score * 0.72 + artist_score * 0.28

    penalty = _orientation_conflict_penalty(
        input_title=title,
        input_artist=artist,
        candidate_title=cand_title,
        candidate_artists=cand_artists,
    )

    if orientation == "original":
        score -= penalty
    elif orientation == "swapped":
        score += penalty * 0.6

    bad_tokens = ["instrumental", "remix", "live", "sped up", "slowed", "karaoke"]
    cand_title_norm = _normalize_text(cand_title)
    if any(token in cand_title_norm for token in bad_tokens):
        score -= 0.05

    if artist and artist.strip():
        if artist_score < 0.20 and title_score < 0.90:
            score -= 0.08

    return round(score, 4)


def _build_search_cases(title: str, artist: Optional[str]) -> List[Tuple[str, Optional[str]]]:
    raw_title = (title or "").strip()
    clean_title = _clean_track_title_for_search(raw_title)

    title_variants: List[str] = []
    for value in [raw_title, clean_title]:
        if value and value not in title_variants:
            title_variants.append(value)

    artist_variants = _artist_variants(artist)

    cases: List[Tuple[str, Optional[str]]] = []

    # title + artist
    for t in title_variants:
        for a in artist_variants:
            if t and a:
                cases.append((t, a))

    # title only
    for t in title_variants:
        if t:
            cases.append((t, None))

    deduped: List[Tuple[str, Optional[str]]] = []
    seen = set()
    for case in cases:
        if case not in seen:
            seen.add(case)
            deduped.append(case)

    return deduped


def _collect_candidates(
    access_token: str,
    input_title: str,
    input_artist: Optional[str],
    market: Optional[str],
    orientation: str,
    per_query_limit: int = 5,
) -> List[Dict[str, Any]]:
    seen_ids = set()
    ranked: List[Dict[str, Any]] = []

    search_cases = _build_search_cases(input_title, input_artist)

    for search_title, search_artist in search_cases:
        candidates = search_track(
            access_token=access_token,
            title=search_title,
            artist=search_artist,
            market=market,
            limit=per_query_limit,
        )

        for candidate in candidates:
            candidate_id = candidate.get("id")
            if not candidate_id or candidate_id in seen_ids:
                continue

            seen_ids.add(candidate_id)

            cand_artists = [a.get("name", "") for a in candidate.get("artists", [])]
            score = _candidate_score(
                candidate=candidate,
                title=input_title,
                artist=input_artist,
                orientation=orientation,
            )

            ranked.append({
                "id": candidate_id,
                "uri": candidate.get("uri", ""),
                "name": candidate.get("name", ""),
                "artists": cand_artists,
                "score": score,
                "orientation": orientation,
                "search_title": search_title,
                "search_artist": search_artist or "",
                "input_artist": input_artist or "",
                "input_title": input_title or "",
            })

    return ranked


def _merge_and_rank_candidates(
    original_candidates: List[Dict[str, Any]],
    swapped_candidates: List[Dict[str, Any]],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for item in original_candidates + swapped_candidates:
        track_id = item["id"]
        existing = merged.get(track_id)

        if not existing or item["score"] > existing["score"]:
            merged[track_id] = item

    ranked = list(merged.values())
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


def _should_use_llm_rerank(candidates: List[Dict[str, Any]]) -> bool:
    if len(candidates) < 2:
        return False

    best = candidates[0]["score"]
    second = candidates[1]["score"]
    margin = best - second

    if best < 0.84:
        return True

    if margin < 0.05:
        return True

    return False


def _apply_llm_rerank_if_needed(
    original_artist: Optional[str],
    original_title: str,
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    if not _should_use_llm_rerank(candidates):
        return None

    llm_candidates = []
    for idx, item in enumerate(candidates):
        llm_candidates.append({
            "index": idx,
            "name": item["name"],
            "artists": item["artists"],
            "score": item["score"],
            "orientation": item["orientation"],
        })

    decision = rerank_spotify_candidates_with_llm(
        input_artist=original_artist or "",
        input_title=original_title or "",
        candidates=llm_candidates,
    )

    if not decision:
        return None

    picked_index = decision.get("picked_index", -1)
    confidence = decision.get("confidence", "low")

    if not isinstance(picked_index, int):
        return None

    if picked_index < 0 or picked_index >= len(candidates):
        return None

    selected = dict(candidates[picked_index])
    selected["llm_reranked"] = True
    selected["llm_confidence"] = confidence
    selected["llm_reason"] = decision.get("reason", "")
    selected["llm_should_swap"] = bool(decision.get("should_swap", False))
    return selected


def pick_best_track_match(
    access_token: str,
    title: str,
    artist: Optional[str] = None,
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    original_title = (title or "").strip()
    original_artist = (artist or "").strip() or None

    if not original_title:
        return None

    original_candidates = _collect_candidates(
        access_token=access_token,
        input_title=original_title,
        input_artist=original_artist,
        market=market,
        orientation="original",
        per_query_limit=5,
    )

    swapped_candidates: List[Dict[str, Any]] = []
    if original_artist:
        swapped_candidates = _collect_candidates(
            access_token=access_token,
            input_title=original_artist,
            input_artist=original_title,
            market=market,
            orientation="swapped",
            per_query_limit=5,
        )

    top_candidates = _merge_and_rank_candidates(
        original_candidates=original_candidates,
        swapped_candidates=swapped_candidates,
        top_k=5,
    )

    if not top_candidates:
        return None

    best = top_candidates[0]

    # 1차 규칙 기반 컷
    base_threshold = 0.66
    swapped_threshold = 0.72

    if best["orientation"] == "swapped" and best["score"] < swapped_threshold:
        llm_selected = _apply_llm_rerank_if_needed(
            original_artist=original_artist,
            original_title=original_title,
            candidates=top_candidates,
        )
        if llm_selected:
            best = llm_selected
        else:
            return None

    elif best["score"] < base_threshold:
        llm_selected = _apply_llm_rerank_if_needed(
            original_artist=original_artist,
            original_title=original_title,
            candidates=top_candidates,
        )
        if llm_selected:
            best = llm_selected
        else:
            return None

    else:
        llm_selected = _apply_llm_rerank_if_needed(
            original_artist=original_artist,
            original_title=original_title,
            candidates=top_candidates,
        )
        if llm_selected:
            best = llm_selected

    # 최종 안정성 체크
    final_threshold = swapped_threshold if best["orientation"] == "swapped" else base_threshold
    if best["score"] < final_threshold and not best.get("llm_reranked"):
        return None

    if best["score"] < 0.60:
        return None

    best["top_candidates"] = top_candidates
    return best