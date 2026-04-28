from app.clients.youtube_client import collect_text_sources
from app.acr.acr_pipeline import extract_songs_with_acr
from app.services.fallback_extraction import extract_songs_with_ocr
from app.services.text_analysis import analyze_comments, analyze_description


def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_text = source_data.get("description", "")
    comments = source_data.get("comments", [])

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
            "debug": {
                "description": description_result,
            },
        }

    comments_result = analyze_comments(comments)
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
            "debug": {
                "description": description_result,
                "comments": comments_result,
            },
        }

    return {
        "input_url": source_data["input_url"],
        "video_id": source_data["video_id"],
        "youtube_title": source_data.get("youtube_title", ""),
        "selected_stage": "text",
        "text_stage": "none",
        "success": False,
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
