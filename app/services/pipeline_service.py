# 전체 흐름 연결
# 설명란 분석 실패 -> 댓글로 넘어가기

from app.services.text_analysis import analyze_comments, analyze_description
from app.services.youtube_service import collect_text_sources


def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_result = analyze_description(source_data["description"])
    if description_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "selected_stage": "description",
            "success": True,
            "songs": description_result["songs"],
            "debug": {
                "description": description_result,
            },
        }

    comments_result = analyze_comments(source_data["comments"])
    if comments_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "selected_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
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
        "debug": {
            "description": description_result,
            "comments": comments_result,
        },
    }