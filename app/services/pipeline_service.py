from app.clients.youtube_client import collect_text_sources
from app.acr.acr_pipeline import extract_songs_with_acr
from app.services.fallback_extraction import extract_songs_with_ocr
from app.services.text_analysis import analyze_comments_prioritized, analyze_description

_AI_PLAYLIST_KEYWORDS = [
    # 한국어
    "ai 음악", "ai음악", "인공지능 음악", "인공지능음악",
    "ai로 만든", "ai가 만든", "ai 커버", "ai커버",
    "ai 생성", "ai생성", "ai 제작", "ai제작",
    "ai 노래", "ai노래",
    # 영어
    "ai generated", "ai-generated", "ai music", "ai cover", "ai song",
    "suno", "udio", "artificial intelligence music",
]


def _detect_ai_playlist(title: str, description: str, comments: list) -> bool:
    texts = [title.lower(), description.lower()]
    for c in comments[:10]:
        text = (c.get("text", "") if isinstance(c, dict) else str(c)).lower()
        texts.append(text)
    combined = " ".join(texts)
    return any(kw in combined for kw in _AI_PLAYLIST_KEYWORDS)


def _fallback_recommendation(description_result: dict, comments_result: dict) -> dict:
    signals = {
        "description": description_result.get("signals", {}),
        "comments": comments_result.get("signals", {}),
    }
    failure_reasons = [
        reason
        for reason in [
            description_result.get("failure_reason"),
            comments_result.get("failure_reason"),
        ]
        if reason
    ]
    visible_tracklist_possible = any(
        (item or {}).get("timestamp_count", 0) >= 2
        or (item or {}).get("pattern_count", 0) >= 2
        or bool((item or {}).get("has_tracklist_structure"))
        for item in signals.values()
    )
    text_is_noisy_or_empty = all(
        reason in {"too_short", "no_timestamps", "no_pattern", "noisy_comments", "too_few_songs_without_pattern"}
        for reason in failure_reasons
    ) if failure_reasons else True

    if visible_tracklist_possible:
        return {
            "recommended_stage": "ocr",
            "reason": "visible_tracklist_possible",
            "message": "description/comments에서 패턴 신호는 보이지만 곡 추출이 부족합니다. 화면에 트랙리스트가 있을 가능성이 있어 OCR을 먼저 추천합니다.",
            "acr_limit_notice": "",
        }

    if text_is_noisy_or_empty:
        return {
            "recommended_stage": "acr",
            "reason": "no_text_or_visible_tracklist_signal",
            "message": "description/comments에서 곡 정보 신호가 약합니다. 화면에도 트랙리스트 단서가 없으면 ACR 오디오 인식을 추천합니다.",
            "acr_limit_notice": "ACR은 서비스 DB에 등록되지 않은 음원, 짧은 구간, 전환부에서는 인식하지 못할 수 있습니다.",
        }

    return {
        "recommended_stage": "ocr",
        "reason": "low_completeness_or_pattern_gap",
        "message": "텍스트 곡 정보가 불완전합니다. 화면 트랙리스트가 있다면 OCR을 추천합니다.",
        "acr_limit_notice": "",
    }


def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_text = source_data.get("description", "")
    comments = source_data.get("comment_items") or source_data.get("comments", [])
    youtube_title = source_data.get("youtube_title", "")

    if _detect_ai_playlist(youtube_title, description_text, comments):
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": youtube_title,
            "selected_stage": "text",
            "text_stage": "none",
            "success": False,
            "failure_reason": "ai_playlist",
            "is_ai_playlist": True,
            "fallback_recommendation": {},
            "songs": [],
            "ocr_used": False,
            "acr_used": False,
            "signals": {},
            "metrics": {},
            "debug": {},
        }

    description_result = analyze_description(description_text)
    if description_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "description",
            "success": True,
            "songs": description_result["songs"],
            "ocr_used": False,
            "acr_used": False,
            "signals": description_result["signals"],
            "metrics": description_result["metrics"],
            "failure_reason": "",
            "is_partial_but_valid": description_result.get("is_partial_but_valid", False),
            "validity_reason": description_result.get("validity_reason", ""),
            "debug": {
                "description": description_result,
            },
        }

    comments_result = analyze_comments_prioritized(comments)
    if comments_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "text",
            "text_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
            "ocr_used": False,
            "acr_used": False,
            "signals": comments_result["signals"],
            "metrics": comments_result["metrics"],
            "failure_reason": "",
            "is_partial_but_valid": comments_result.get("is_partial_but_valid", False),
            "validity_reason": comments_result.get("validity_reason", ""),
            "source_priority_used": comments_result.get("source_priority_used", "expanded_comments"),
            "debug": {
                "description": description_result,
                "comments": comments_result,
            },
        }

    fallback_recommendation = _fallback_recommendation(description_result, comments_result)
    return {
        "input_url": source_data["input_url"],
        "video_id": source_data["video_id"],
        "youtube_title": source_data.get("youtube_title", ""),
        "selected_stage": "text",
        "text_stage": "none",
        "success": False,
        "failure_reason": comments_result.get("failure_reason") or description_result.get("failure_reason") or "no_pattern",
        "fallback_recommendation": fallback_recommendation,
        "source_priority_used": comments_result.get("source_priority_used", "expanded_comments"),
        "songs": [],
        "ocr_used": False,
        "acr_used": False,
        "signals": {
            "description": description_result["signals"],
            "comments": comments_result["signals"],
        },
        "metrics": {
            "description": description_result["metrics"],
            "comments": comments_result["metrics"],
        },
        "debug": {
            "description": description_result,
            "comments": comments_result,
        },
    }


def run_youtube_pipeline(url: str, mode: str = "text") -> dict:
    mode = (mode or "text").strip().lower()

    if mode == "ocr":
        result = extract_songs_with_ocr(url)
        result["input_url"] = url
        result["mode"] = "ocr"
        return result

    if mode == "acr":
        result = extract_songs_with_acr(url)
        result["input_url"] = url
        result["mode"] = "acr"
        return result

    text_result = run_youtube_text_pipeline(url)
    text_result["mode"] = "text"
    text_result["selected_stage"] = "text"
    text_result["ocr_used"] = False
    text_result["acr_used"] = False
    return text_result
