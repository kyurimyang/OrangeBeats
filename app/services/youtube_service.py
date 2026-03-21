# 유튜브에서 설명란/댓글 모아서 한 번에 반환

from app.clients.youtube_client import collect_youtube_texts
from app.constants.pipeline_params import COMMENT_LIMIT_DEFAULT


def collect_text_sources(url: str) -> dict:
    data = collect_youtube_texts(url)

    return {
        "input_url": url,
        "video_id": data["video_id"],
        "description": data["description"],
        "comments": data["comments"][:COMMENT_LIMIT_DEFAULT],##댓글개수제한적용
    }