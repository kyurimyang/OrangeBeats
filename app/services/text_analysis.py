from app.clients.openai_client import extract_songs_with_llm
from app.parsers.song_parser import (
    assess_text_stage_validity,
    count_text_signals,
    normalize_song_candidates,
    parse_json_from_text,
    parse_unstructured_lines_to_json,
)


def _normalize_evidence_confidence(value: object, default: str = "medium") -> str:
    confidence = str(value or default).strip().lower()
    return confidence if confidence in {"high", "medium", "low"} else default


def _infer_evidence_type(raw_line: str) -> str:
    if _comment_has_timestamp(raw_line):
        return "timestamp_pair" if _comment_has_track_pattern(raw_line) else "title_only_timestamp"
    if _comment_has_track_pattern(raw_line):
        return "delimiter_pair"
    return "other"


def _title_from_timestamp_only_line(raw_line: str) -> str:
    import re

    value = str(raw_line or "").strip()
    value = re.sub(r'^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*[-–—]?\s*', '', value)
    return value.strip()


def _timestamp_line_lacks_pair_delimiter(raw_line: str) -> bool:
    import re

    if not _comment_has_timestamp(raw_line):
        return False
    tail = _title_from_timestamp_only_line(raw_line)
    if not tail:
        return False
    return not bool(re.search(r"\s[-–—~|/]\s|:\s", tail))


def _source_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _raw_line_in_source(raw_line: str, source_text: str) -> bool:
    raw_line = str(raw_line or "").strip()
    if not raw_line:
        return False
    return raw_line in (source_text or "")


def _annotate_song_evidence(
    songs: list[dict],
    *,
    source_text: str,
    source_name: str,
    method: str,
    require_raw_line: bool = False,
) -> list[dict]:
    lines = _source_lines(source_text)
    annotated: list[dict] = []
    for song in songs or []:
        item = dict(song)
        raw_line = str(item.get("raw_line") or item.get("raw") or "").strip()
        if method == "llm" and raw_line and not _raw_line_in_source(raw_line, source_text):
            title = str(item.get("title") or "").strip()
            artist = str(item.get("artist") or "").strip()
            raw_line = next(
                (
                    line
                    for line in lines
                    if (title and title in line) or (artist and artist in line)
                ),
                "",
            )
            if not raw_line:
                continue
        if require_raw_line and not _raw_line_in_source(raw_line, source_text):
            continue
        if not raw_line:
            title = str(item.get("title") or "").strip()
            raw_line = next((line for line in lines if title and title in line), "")
        item["raw_line"] = raw_line
        item["line_index"] = lines.index(raw_line) if raw_line in lines else item.get("line_index", -1)
        item["source"] = item.get("source") or source_name
        item["source_mode"] = item.get("source_mode") or source_name
        item["evidence_type"] = item.get("evidence_type") or _infer_evidence_type(raw_line)
        if _timestamp_line_lacks_pair_delimiter(raw_line):
            item["evidence_type"] = "title_only_timestamp"
        if item["evidence_type"] == "title_only_timestamp":
            timestamp_title = _title_from_timestamp_only_line(raw_line)
            if timestamp_title:
                item["title"] = timestamp_title
                item["artist"] = timestamp_title
                item["artist_exists"] = True
                item["title_exists"] = True
                item["is_complete"] = True
                item["completeness_score"] = max(float(item.get("completeness_score") or 0.0), 1.0)
                item["timestamp_title_normalized"] = True
        item["confidence"] = _normalize_evidence_confidence(
            item.get("confidence"),
            "high" if method == "rule_based" and raw_line else "medium",
        )
        annotated.append(item)
    return annotated


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


def _run_llm_parse(text: str, llm_blocks: list[str] | None, stage: str, inferred_artist: str, rule_signals: dict) -> dict:
    llm_raw = extract_songs_with_llm(llm_blocks if llm_blocks is not None else [text])
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json, inferred_artist=inferred_artist, skip_direction_detection=True)
    llm_result['songs'] = _annotate_song_evidence(
        llm_result['songs'], source_text=text, source_name=stage, method='llm', require_raw_line=False,
    )
    validity = assess_text_stage_validity(text, llm_result['songs'])
    return {
        'stage': stage,
        'success': validity['success'],
        'method': 'llm',
        'signals': rule_signals,
        'metrics': _build_song_metrics(llm_result['songs']),
        'failure_reason': '' if validity['success'] else validity['failure_reason'],
        'is_partial_but_valid': validity['is_partial_but_valid'],
        'validity_reason': validity['validity_reason'],
        'songs': llm_result['songs'],
    }


def _run_rule_parse(text: str, stage: str, inferred_artist: str, rule_signals: dict) -> dict:
    rule_result = parse_unstructured_lines_to_json(text)
    rule_result = normalize_song_candidates(rule_result, inferred_artist=inferred_artist)
    rule_result['songs'] = _annotate_song_evidence(
        rule_result['songs'], source_text=text, source_name=stage, method='rule_based',
    )
    validity = assess_text_stage_validity(text, rule_result['songs'])
    return {
        'stage': stage,
        'success': validity['success'],
        'method': 'rule_based',
        'signals': rule_signals,
        'metrics': _build_song_metrics(rule_result['songs']),
        'failure_reason': '' if validity['success'] else validity['failure_reason'],
        'is_partial_but_valid': validity['is_partial_but_valid'],
        'validity_reason': validity['validity_reason'],
        'songs': rule_result['songs'],
    }


def analyze_text_block(
    text: str,
    *,
    stage: str,
    llm_blocks: list[str] | None = None,
    inferred_artist: str = "",
) -> dict:
    text = text or ""
    rule_signals = count_text_signals(text)

    # 규칙 기반 + direction LLM 우선, 실패 시 LLM full parsing fallback
    result = _run_rule_parse(text, stage, inferred_artist, rule_signals)
    if result['success']:
        return result
    return _run_llm_parse(text, llm_blocks, stage, inferred_artist, rule_signals)


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
        combined = '\n'.join(blocks)
        signals = count_text_signals(combined)
        if not signals.get('has_tracklist_structure'):
            continue

        result = analyze_text_block(
            combined,
            stage='comments',
            llm_blocks=blocks[:20],
            inferred_artist=inferred_artist,
        )
        result['source_priority_used'] = source_priority
        attempts.append(result)
        if result['success']:
            result['debug_attempts'] = attempts
            return result

    if not attempts:
        return {
            'stage': 'comments',
            'success': False,
            'method': 'skipped',
            'signals': count_text_signals('\n'.join(
                _comment_text(c) for c in comments if _comment_text(c)
            )),
            'metrics': {},
            'failure_reason': 'noisy_comments',
            'is_partial_but_valid': False,
            'validity_reason': '',
            'songs': [],
            'source_priority_used': 'expanded_comments' if comments else 'none',
            'debug_attempts': [],
        }

    fallback = attempts[-1]
    if not fallback.get('songs') and len(comments) >= 10:
        signals = fallback.get('signals') or {}
        if not signals.get('timestamp_count') and not signals.get('pattern_count'):
            fallback['failure_reason'] = 'noisy_comments'
    fallback['source_priority_used'] = fallback.get('source_priority_used') or 'expanded_comments'
    fallback['debug_attempts'] = attempts
    return fallback
