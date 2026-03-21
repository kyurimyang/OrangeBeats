from urllib.parse import parse_qs, urlparse

import requests
from fastapi import HTTPException

from app.config import YOUTUBE_API_KEY

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def parse_youtube_target(input_value: str) -> dict[str, str]:
    value = input_value.strip()
    parsed = urlparse(value)

    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        playlist_id = query.get("list", [None])[0]
        video_id = query.get("v", [None])[0]

        if not playlist_id and video_id:
            return {"type": "video", "id": video_id}

        if playlist_id and playlist_id.startswith("RD") and video_id:
            return {"type": "video", "id": video_id}

        if playlist_id:
            return {"type": "playlist", "id": playlist_id}

        if "youtu.be" in parsed.netloc and parsed.path.strip("/"):
            return {"type": "video", "id": parsed.path.strip("/")}

        raise HTTPException(
            status_code=400,
            detail="YouTube URL에서 처리 가능한 v/list 파라미터를 찾지 못했습니다."
        )

    if value.startswith(("PL", "UU", "LL", "OLAK")):
        return {"type": "playlist", "id": value}

    if len(value) == 11:
        return {"type": "video", "id": value}

    raise HTTPException(
        status_code=400,
        detail="지원하지 않는 YouTube 입력 형식입니다."
    )


def _youtube_get(path: str, params: dict) -> dict:
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY가 비어 있습니다.")

    response = requests.get(
        f"{YOUTUBE_API_BASE}/{path}",
        params={**params, "key": YOUTUBE_API_KEY},
        timeout=15,
    )

    if response.status_code >= 400:
        try:
            message = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            message = response.text

        raise HTTPException(
            status_code=response.status_code,
            detail=f"YouTube API 오류: {message}"
        )

    return response.json()


def get_playlist_video_ids(playlist_id: str, max_videos: int = 5) -> list[str]:
    video_ids: list[str] = []
    next_page_token = None

    while len(video_ids) < max_videos:
        payload = _youtube_get(
            "playlistItems",
            {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": min(50, max_videos - len(video_ids)),
                "pageToken": next_page_token,
            },
        )

        for item in payload.get("items", []):
            video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
            if len(video_ids) >= max_videos:
                break

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids


def get_video_description(video_id: str) -> str:
    payload = _youtube_get(
        "videos",
        {
            "part": "snippet",
            "id": video_id,
        },
    )

    items = payload.get("items", [])
    if not items:
        return ""

    return items[0].get("snippet", {}).get("description", "").strip()


def get_video_comments(video_id: str, max_comments: int = 20) -> list[str]:
    comments: list[str] = []
    next_page_token = None

    while len(comments) < max_comments:
        try:
            payload = _youtube_get(
                "commentThreads",
                {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, max_comments - len(comments)),
                    "order": "relevance",
                    "textFormat": "plainText",
                    "pageToken": next_page_token,
                },
            )
        except HTTPException as exc:
            if exc.status_code in (403, 404):
                return comments
            raise

        for item in payload.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = snippet.get("textDisplay", "").strip()
            if text:
                comments.append(text)

            if len(comments) >= max_comments:
                break

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return comments


def collect_youtube_texts(
    input_value: str,
    max_videos: int = 5,
    max_comments_per_video: int = 20,
) -> dict:
    target = parse_youtube_target(input_value)

    if target["type"] == "playlist":
        playlist_id = target["id"]
        video_ids = get_playlist_video_ids(playlist_id, max_videos=max_videos)
    else:
        playlist_id = ""
        video_ids = [target["id"]]

    if not video_ids:
        return {
            "target_type": target["type"],
            "playlist_id": playlist_id,
            "video_ids": [],
            "description": "",
            "comments": [],
        }

    # MVP 기준: 첫 번째 영상 설명란 우선 사용
    first_video_id = video_ids[0]
    description = get_video_description(first_video_id)

    all_comments: list[str] = []
    for video_id in video_ids:
        all_comments.extend(
            get_video_comments(video_id, max_comments=max_comments_per_video)
        )

    return {
        "target_type": target["type"],
        "playlist_id": playlist_id,
        "video_ids": video_ids,
        "description": description,
        "comments": all_comments,
    }