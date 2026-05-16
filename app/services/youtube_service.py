# 유튜브에서 설명란/댓글 모아서 한 번에 반환

from app.clients.youtube_client import collect_text_sources
from app.constants.pipeline_params import COMMENT_LIMIT_DEFAULT


def collect_text_final(url: str) -> dict:
    data = collect_text_sources(url)

    return {
        "input_url": url,
        "video_id": data["video_id"],
        "channel_id": data.get("channel_id", ""),
        "youtube_title": data.get("youtube_title", ""),
        "description": data["description"],
        "comments": data["comments"][:COMMENT_LIMIT_DEFAULT],
        "comment_items": data.get("comment_items", [])[:COMMENT_LIMIT_DEFAULT],
        "author_comment_items": data.get("author_comment_items", []),
        "author_comments": data.get("author_comments", []),
    }