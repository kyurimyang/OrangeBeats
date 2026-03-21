from app.services.text_analysis_service import analyze_comments, analyze_description
from app.services.youtube_service import collect_text_sources


def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_result = analyze_description(source_data["description"])
    if description_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "target_type": source_data["target_type"],
            "playlist_id": source_data["playlist_id"],
            "video_ids": source_data["video_ids"],
            "description_length": len(source_data["description"]),
            "comment_count": len(source_data["comments"]),
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
            "target_type": source_data["target_type"],
            "playlist_id": source_data["playlist_id"],
            "video_ids": source_data["video_ids"],
            "description_length": len(source_data["description"]),
            "comment_count": len(source_data["comments"]),
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
        "target_type": source_data["target_type"],
        "playlist_id": source_data["playlist_id"],
        "video_ids": source_data["video_ids"],
        "description_length": len(source_data["description"]),
        "comment_count": len(source_data["comments"]),
        "selected_stage": "none",
        "success": False,
        "songs": [],
        "debug": {
            "description": description_result,
            "comments": comments_result,
        },
    }