# 설명란/댓글 분석 -> songs 리스트로 변환

from app.clients.openai_client import extract_songs_with_llm
from app.parsers.song_parser import (
    count_text_signals,
    is_text_stage_success,
    normalize_song_candidates,
    parse_json_from_text,
    parse_unstructured_lines_to_json,
)

# 곡 리스트 기준 메트릭 계산 (추가)
def _build_song_metrics(songs: list[dict]) -> dict:
    total_count = len(songs)
    complete_count = sum(1 for song in songs if song.get("is_complete"))
    avg_completeness = (
        sum(song.get("completeness_score", 0.0) for song in songs) / total_count
        if total_count > 0 else 0.0
    )

    return {
        "song_count": total_count,
        "complete_song_count": complete_count,
        "avg_completeness": round(avg_completeness, 3),
    }

# 설명란 분석 (규칙 기반 우선, 부족하면 LLM 호출)
def analyze_description(description: str) -> dict:
    rule_based = parse_unstructured_lines_to_json(description)
    rule_based = normalize_song_candidates(rule_based)

    rule_success = is_text_stage_success(description, rule_based["songs"])
    rule_metrics = _build_song_metrics(rule_based["songs"])
    rule_signals = count_text_signals(description)

    if rule_success:
        return {
            "stage": "description",
            "success": True,
            "method": "rule_based",
            "signals": rule_signals,
            "metrics": rule_metrics,
            "songs": rule_based["songs"],
        }

    llm_raw = extract_songs_with_llm([description])
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json)

    llm_success = is_text_stage_success(description, llm_result["songs"])
    llm_metrics = _build_song_metrics(llm_result["songs"])

    return {
        "stage": "description",
        "success": llm_success,
        "method": "llm",
        "signals": rule_signals,
        "metrics": llm_metrics,
        "songs": llm_result["songs"],
    }


# 댓글 분석 (LLM 중심 분석)
def analyze_comments(comments: list[str]) -> dict:
    comment_text = "\n".join(comments)

    llm_raw = extract_songs_with_llm(comments)
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json)

    llm_success = is_text_stage_success(comment_text, llm_result["songs"])
    llm_metrics = _build_song_metrics(llm_result["songs"])
    llm_signals = count_text_signals(comment_text)

    return {
        "stage": "comments",
        "success": llm_success,
        "method": "llm",
        "signals": llm_signals,
        "metrics": llm_metrics,
        "songs": llm_result["songs"],
    }
    
    