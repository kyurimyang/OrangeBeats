from app.clients.openai_client import extract_songs_with_llm
from app.parsers.song_parser import (
    assess_text_stage_validity,
    count_text_signals,
    is_text_stage_success,
    normalize_song_candidates,
    parse_json_from_text,
    parse_unstructured_lines_to_json,
)


def _build_song_metrics(songs: list[dict]) -> dict:
    total_count = len(songs)
    complete_count = sum(1 for song in songs if song.get('is_complete'))
    avg_completeness = (
        sum(song.get('completeness_score', 0.0) for song in songs) / total_count
        if total_count > 0 else 0.0
    )

    return {
        'song_count': total_count,
        'complete_song_count': complete_count,
        'avg_completeness': round(avg_completeness, 3),
    }


def analyze_text_block(
    text: str,
    *,
    stage: str,
    llm_blocks: list[str] | None = None,
    inferred_artist: str = "",
) -> dict:
    text = text or ""
    rule_based = parse_unstructured_lines_to_json(text)
    rule_based = normalize_song_candidates(rule_based, inferred_artist=inferred_artist)

    rule_validity = assess_text_stage_validity(text, rule_based['songs'])
    rule_success = rule_validity["success"]
    rule_metrics = _build_song_metrics(rule_based['songs'])
    rule_signals = count_text_signals(text)

    if rule_success:
        return {
            'stage': stage,
            'success': True,
            'method': 'rule_based',
            'signals': rule_signals,
            'metrics': rule_metrics,
            'failure_reason': '',
            'is_partial_but_valid': rule_validity['is_partial_but_valid'],
            'validity_reason': rule_validity['validity_reason'],
            'songs': rule_based['songs'],
        }

    llm_raw = extract_songs_with_llm(llm_blocks if llm_blocks is not None else [text])
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json, inferred_artist=inferred_artist)

    llm_validity = assess_text_stage_validity(text, llm_result['songs'])
    llm_success = llm_validity["success"]
    llm_metrics = _build_song_metrics(llm_result['songs'])

    return {
        'stage': stage,
        'success': llm_success,
        'method': 'llm',
        'signals': rule_signals,
        'metrics': llm_metrics,
        'failure_reason': '' if llm_success else llm_validity['failure_reason'],
        'is_partial_but_valid': llm_validity['is_partial_but_valid'],
        'validity_reason': llm_validity['validity_reason'],
        'songs': llm_result['songs'],
    }


def analyze_description(description: str, inferred_artist: str = "") -> dict:
    return analyze_text_block(description, stage='description', inferred_artist=inferred_artist)


def analyze_comments(comments: list[str], inferred_artist: str = "") -> dict:
    comment_text = '\n'.join(comments)
    return analyze_text_block(comment_text, stage='comments', llm_blocks=comments[:20], inferred_artist=inferred_artist)


def _comment_text(comment: str | dict) -> str:
    if isinstance(comment, dict):
        return str(comment.get('text') or comment.get('textDisplay') or '')
    return str(comment or '')


def _comment_likes(comment: str | dict) -> int:
    if isinstance(comment, dict):
        try:
            return int(comment.get('like_count') or comment.get('likeCount') or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _comment_has_timestamp(text: str) -> bool:
    import re
    return bool(re.search(r'(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)', text or ''))


def _comment_has_track_pattern(text: str) -> bool:
    signals = count_text_signals(text or '')
    return bool(signals.get('timestamp_count') or signals.get('pattern_count') or signals.get('has_tracklist_structure'))


def _ordered_comment_sources(comments: list[str | dict]) -> list[tuple[str, list[str]]]:
    texts = [_comment_text(comment).strip() for comment in comments if _comment_text(comment).strip()]
    if not texts:
        return []

    groups: list[tuple[str, list[str]]] = []

    # 작성자 본인 댓글을 최우선으로 시도 (트랙 패턴이 있는 경우)
    author_texts = [
        _comment_text(c).strip()
        for c in comments
        if isinstance(c, dict) and c.get("is_author_comment") and _comment_text(c).strip()
    ]
    if author_texts and any(_comment_has_track_pattern(t) for t in author_texts):
        groups.append(("author_comment", author_texts))

    first = texts[0]
    if _comment_has_track_pattern(first):
        groups.append(('pinned_comment', [first]))

    liked_comments = sorted(
        comments,
        key=lambda item: _comment_likes(item),
        reverse=True,
    )
    top_liked = [_comment_text(item).strip() for item in liked_comments[:3] if _comment_text(item).strip()]
    top_liked = [text for text in top_liked if _comment_has_track_pattern(text)]
    if top_liked:
        groups.append(('top_liked_comment', top_liked))

    timestamp_comments = [text for text in texts if _comment_has_timestamp(text)]
    if timestamp_comments:
        groups.append(('timestamp_comments', timestamp_comments[:10]))

    groups.append(('expanded_comments', texts[:30]))

    deduped: list[tuple[str, list[str]]] = []
    seen_payloads: set[str] = set()
    for name, payload in groups:
        key = '\n'.join(payload)
        if not key or key in seen_payloads:
            continue
        seen_payloads.add(key)
        deduped.append((name, payload))
    return deduped


def analyze_comments_prioritized(comments: list[str | dict], inferred_artist: str = "") -> dict:
    attempts = []
    for source_priority, blocks in _ordered_comment_sources(comments):
        result = analyze_text_block(
            '\n'.join(blocks),
            stage='comments',
            llm_blocks=blocks[:20],
            inferred_artist=inferred_artist,
        )
        result['source_priority_used'] = source_priority
        attempts.append(result)
        if result['success']:
            result['debug_attempts'] = attempts
            return result

    fallback = attempts[-1] if attempts else analyze_text_block('', stage='comments', llm_blocks=[], inferred_artist=inferred_artist)
    if not fallback.get('songs') and len(comments) >= 10:
        signals = fallback.get('signals') or {}
        if not signals.get('timestamp_count') and not signals.get('pattern_count'):
            fallback['failure_reason'] = 'noisy_comments'
    fallback['source_priority_used'] = fallback.get('source_priority_used') or 'expanded_comments'
    fallback['debug_attempts'] = attempts
    return fallback
