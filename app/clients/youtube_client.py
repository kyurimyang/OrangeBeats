# Youtube API 호출
# Youtube에서 텍스트 긁어오기

from urllib.parse import parse_qs, urlparse

import requests
from fastapi import HTTPException

from app.config import YOUTUBE_API_KEY

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


# 입력값이 video URL인지 playlist URL인지 판별하고 id 추출
def parse_youtube_target(input_value: str) -> dict[str, str]:
    value = input_value.strip()
    parsed = urlparse(value)

    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        playlist_id = query.get("list", [None])[0]
        video_id = query.get("v", [None])[0]

        # 일반 영상
        if not playlist_id and video_id:
            return {"type": "video", "id": video_id}

        # RD 믹스 → 영상 취급
        if playlist_id and playlist_id.startswith("RD") and video_id:
            return {"type": "video", "id": video_id}

        # 플레이리스트
        if playlist_id:
            return {"type": "playlist", "id": playlist_id}

        # youtu.be
        if "youtu.be" in parsed.netloc and parsed.path.strip("/"):
            return {"type": "video", "id": parsed.path.strip("/")}

        raise HTTPException(status_code=400, detail="유효한 YouTube URL이 아님")

    # ID 직접 입력
    if value.startswith(("PL", "UU", "LL", "OLAK")):
        return {"type": "playlist", "id": value}

    if len(value) == 11:
        return {"type": "video", "id": value}

    raise HTTPException(status_code=400, detail="지원하지 않는 형식")


# YouTube Data API 공통 GET 요청
def _youtube_get(path: str, params: dict) -> dict:
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="API 키 없음")

    try:
        response = requests.get(
            f"{YOUTUBE_API_BASE}/{path}",
            params={**params, "key": YOUTUBE_API_KEY},
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(status_code=500, detail="YouTube 요청 실패")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail="YouTube API 오류")

    return response.json()


# video_id 기준 설명란 가져오기
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

    return items[0]["snippet"].get("description", "")


# video_id 기준 댓글 가져오기
def get_video_comments(video_id: str, max_comments: int = 30) -> list[str]:
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        try:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "textFormat": "plainText",
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            payload = _youtube_get("commentThreads", params)

        except HTTPException:
            return comments

        for item in payload.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)

            if len(comments) >= max_comments:
                break

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return comments


# playlist의 첫 번째 영상 id 가져오기
def get_first_video_id_from_playlist(playlist_id: str) -> str:
    payload = _youtube_get(
        "playlistItems",
        {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 1,
        },
    )

    items = payload.get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail="플레이리스트에 영상이 없음")

    return items[0]["snippet"]["resourceId"]["videoId"]


# 최종적으로 설명란/댓글 텍스트 수집
def collect_text_sources(url: str) -> dict:
    target = parse_youtube_target(url)

    if target["type"] == "playlist":
        video_id = get_first_video_id_from_playlist(target["id"])
    else:
        video_id = target["id"]

    description = get_video_description(video_id)
    comments = get_video_comments(video_id)

    return {
        "input_url": url,
        "video_id": video_id,
        "description": description,
        "comments": comments,
    }