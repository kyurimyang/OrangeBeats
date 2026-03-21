from app.clients.youtube_client import collect_youtube_texts
from app.constants.pipeline_params import COMMENT_LIMIT_DEFAULT


def collect_text_sources(url: str) -> dict:
    data = collect_youtube_texts(
        input_value=url,
        max_videos=1,
        max_comments_per_video=COMMENT_LIMIT_DEFAULT,
    )

    return {
        "input_url": url,
        "target_type": data["target_type"],
        "playlist_id": data["playlist_id"],
        "video_ids": data["video_ids"],
        "description": data["description"],
        "comments": data["comments"],
    }