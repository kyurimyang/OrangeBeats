import os
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv
from fastapi import HTTPException
from backend.Pipeline_Params import COMMENT_LIMIT_DEFAULT, COMMENT_LIMIT_MAX

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def parse_youtube_target(input_value: str) -> dict[str, str]:
    """
    입력 링크/ID를 분석해 playlist 또는 video 대상으로 정규화한다.
    - list 없음 + v 있음 -> 단일 영상
    - list가 RD로 시작 + v 있음 -> auto mix/radio이므로 단일 영상으로 처리
    - 그 외 유효한 list -> 플레이리스트
    """
    value = input_value.strip()
    parsed = urlparse(value)

    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        playlist_id = query.get("list", [None])[0]
        video_id = query.get("v", [None])[0]

        # 케이스 1) list 없음 -> 일반 단일 영상
        if not playlist_id and video_id:
            return {"type": "video", "id": video_id}

        # 케이스 2) list=RD... -> auto mix/radio, 영상 단건으로 처리
        if playlist_id and playlist_id.startswith("RD") and video_id:
            return {"type": "video", "id": video_id}

        # 케이스 3) list 있음 -> 플레이리스트
        if playlist_id:
            return {"type": "playlist", "id": playlist_id}

        # 케이스 4) youtu.be/<video_id> -> 단일 영상 
        if "youtu.be" in parsed.netloc and parsed.path.strip("/"):
            return {"type": "video", "id": parsed.path.strip("/")}

        raise HTTPException(status_code=400, detail="YouTube URL에서 처리 가능한 v/list 파라미터를 찾지 못했습니다.")

    # 케이스 5) URL이 아닌 경우: ID prefix 기반 추정
    if value.startswith(("PL", "UU", "LL", "OLAK")):
        return {"type": "playlist", "id": value}

    # 케이스 6) 영상 ID는 일반적으로 11자
    if len(value) == 11:
        return {"type": "video", "id": value}

    raise HTTPException(
        status_code=400,
        detail="지원하지 않는 YouTube 입력 형식입니다. "
    )


def extract_playlist_id(playlist_input: str) -> str:
    """
    입력값을 해석한 뒤 playlist 타입일 때만 playlist ID를 반환한다.
    - playlist URL/ID면 ID 반환
    - video URL/ID면 400 에러
    """
    target = parse_youtube_target(playlist_input)
    if target["type"] != "playlist":
        raise HTTPException(status_code=400, detail="playlist ID 또는 playlist URL을 입력해주세요.")
    return target["id"]


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
        raise HTTPException(status_code=response.status_code, detail=f"YouTube API 오류: {message}")

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


def get_video_comments(video_id: str, max_comments: int = 50) -> list[str]:
    # 댓글 수집 정책: 기본 30, 필요 시 최대 50까지만 허용
    safe_max_comments = max(1, min(max_comments, COMMENT_LIMIT_MAX))
    comments: list[str] = []
    next_page_token = None

    while len(comments) < safe_max_comments:
        try:
            payload = _youtube_get(
                "commentThreads",
                {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, safe_max_comments - len(comments)),
                    "order": "relevance",
                    "textFormat": "plainText",
                    "pageToken": next_page_token,
                },
            )
        except HTTPException as exc:
            # 댓글 비활성화 영상(주로 403)은 건너뛴다.
            if exc.status_code in (403, 404):
                return comments
            raise

        for item in payload.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = snippet.get("textDisplay", "").strip()
            if text:
                comments.append(text)
            if len(comments) >= safe_max_comments:
                break

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return comments


def collect_playlist_comments(
    playlist_input: str,
    max_videos: int = 5,
    max_comments_per_video: int = COMMENT_LIMIT_DEFAULT,
) -> dict:
    """
    YouTube 입력(URL/ID)을 해석해 댓글을 수집한다.
    - playlist 입력이면 영상 목록을 순회하며 댓글 수집
    - video 입력이면 해당 영상 1개 댓글 수집
    반환 구조:
    {
      "playlist_id": "...",
      "video_ids": ["...", "..."],
      "comments": ["...", "..."]
    }
    """
    target = parse_youtube_target(playlist_input)
    safe_max_comments_per_video = max(1, min(max_comments_per_video, COMMENT_LIMIT_MAX))

    if target["type"] == "playlist":
        playlist_id = target["id"]
        video_ids = get_playlist_video_ids(playlist_id, max_videos=max_videos)
    else:
        playlist_id = ""
        video_ids = [target["id"]]

    all_comments: list[str] = []
    for video_id in video_ids:
        all_comments.extend(get_video_comments(video_id, max_comments=safe_max_comments_per_video))

    return {
        "playlist_id": playlist_id,
        "video_ids": video_ids,
        "comments": all_comments,
    }