from app.clients.openai_client import extract_songs_with_llm
from app.parsers.song_parser import (
    count_text_signals,
    is_text_stage_success,
    normalize_song_candidates,
    parse_json_from_text,
    parse_unstructured_lines_to_json,
)


def analyze_description(description: str) -> dict:
    """
    설명란은 규칙 기반 파싱 먼저 시도하고,
    부족하면 LLM 보조 호출.
    """
    rule_based = parse_unstructured_lines_to_json(description)
    rule_based = normalize_song_candidates(rule_based)

    if is_text_stage_success(description, rule_based["songs"]):
        return {
            "stage": "description",
            "success": True,
            "method": "rule_based",
            "signals": count_text_signals(description),
            "songs": rule_based["songs"],
        }

    llm_raw = extract_songs_with_llm([description])
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json)

    return {
        "stage": "description",
        "success": is_text_stage_success(description, llm_result["songs"]),
        "method": "llm",
        "signals": count_text_signals(description),
        "songs": llm_result["songs"],
    }


def analyze_comments(comments: list[str]) -> dict:
    """
    댓글은 기본적으로 LLM 중심 분석.
    """
    comment_text = "\n".join(comments)

    llm_raw = extract_songs_with_llm(comments)
    llm_json = parse_json_from_text(llm_raw)
    llm_result = normalize_song_candidates(llm_json)

    return {
        "stage": "comments",
        "success": is_text_stage_success(comment_text, llm_result["songs"]),
        "method": "llm",
        "signals": count_text_signals(comment_text),
        "songs": llm_result["songs"],
    }