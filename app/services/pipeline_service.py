# 전체 흐름 연결
# 설명란 분석 실패 -> 댓글로 넘어가기

from app.services.text_analysis import analyze_comments, analyze_description
from app.clients.youtube_client import collect_text_sources

# 유튜브 텍스트 파이프라인 전체 실행
def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_text = source_data.get("description", "")
    comments = source_data.get("comments", [])

    description_result = analyze_description(description_text)
    if description_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "selected_stage": "description",
            "success": True,
            "songs": description_result["songs"],
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
            "selected_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
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
        "selected_stage": "none",
        "success": False,
        "songs": [],
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