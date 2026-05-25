# Youtube API 호출
# Youtube에서 텍스트 긁어오기

import time
from collections import OrderedDict
from urllib.parse import parse_qs, urlparse

import requests
from fastapi import HTTPException

from app.config import YOUTUBE_API_KEY

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
_INNERTUBE_BASE = "https://www.youtube.com/youtubei/v1"
_INNERTUBE_CLIENT = {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "ko", "gl": "KR"}
_MAX_CACHE_SIZE = 100
_TEXT_SOURCE_CACHE: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_CACHE_TTL_SECONDS = 3600


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


# video snippet 단일 호출 (title / description / channelId 동시 반환)
def _get_video_snippet(video_id: str) -> dict:
    payload = _youtube_get("videos", {"part": "snippet", "id": video_id})
    items = payload.get("items", [])
    return items[0].get("snippet", {}) if items else {}


# video_id 기준 설명란 가져오기
def get_video_description(video_id: str) -> str:
    return _get_video_snippet(video_id).get("description", "")


# video_id 기준 댓글 가져오기
# channel_id를 전달하면 is_author_comment 필드를 함께 반환
def get_video_comment_items(video_id: str, max_comments: int = 30, channel_id: str = "") -> list[dict]:
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        try:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "textFormat": "plainText",
                "order": "relevance",
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            payload = _youtube_get("commentThreads", params)

        except HTTPException:
            return comments

        for item in payload.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            author_channel_id = (snippet.get("authorChannelId") or {}).get("value", "")
            comments.append(
                {
                    "text": snippet.get("textDisplay", ""),
                    "like_count": int(snippet.get("likeCount") or 0),
                    "published_at": snippet.get("publishedAt", ""),
                    "updated_at": snippet.get("updatedAt", ""),
                    "author_channel_id": author_channel_id,
                    "is_author_comment": bool(channel_id and author_channel_id == channel_id),
                }
            )

            if len(comments) >= max_comments:
                break

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return comments


def get_video_comments(video_id: str, max_comments: int = 30) -> list[str]:
    return [item.get("text", "") for item in get_video_comment_items(video_id, max_comments)]


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


# 최종적으로 설명란/댓글, 제목 텍스트 수집
def collect_text_sources(url: str) -> dict:
    cached = _TEXT_SOURCE_CACHE.get(url)
    if cached:
        data, cached_at = cached
        if time.time() - cached_at < _CACHE_TTL_SECONDS:
            print(f"[youtube_client] cache hit for {url}")
            _TEXT_SOURCE_CACHE.move_to_end(url)
            return data

    target = parse_youtube_target(url)

    channel_id = ""
    youtube_title = ""

    if target["type"] == "playlist":
        playlist_id = target["id"]
        youtube_title = get_playlist_title(playlist_id)
        video_id = get_first_video_id_from_playlist(target["id"])
        # 영상 snippet 단일 호출로 제목 fallback + description + channelId 동시 수집
        snippet = _get_video_snippet(video_id)
        if not youtube_title:
            youtube_title = snippet.get("title", "").strip()
        description = snippet.get("description", "")
        channel_id = snippet.get("channelId", "")
    else:
        video_id = target["id"]
        # 단일 호출로 title / description / channelId 수집 (기존 2회 → 1회)
        snippet = _get_video_snippet(video_id)
        youtube_title = snippet.get("title", "").strip()
        description = snippet.get("description", "")
        channel_id = snippet.get("channelId", "")

    comment_items = get_video_comment_items(video_id, max_comments=50, channel_id=channel_id)
    author_comment_items = [item for item in comment_items if item.get("is_author_comment")]
    author_comments = [item.get("text", "") for item in author_comment_items]
    comments = [item.get("text", "") for item in comment_items]

    result = {
        "input_url": url,
        "video_id": video_id,
        "channel_id": channel_id,
        "youtube_title": youtube_title,
        "description": description,
        "comments": comments,
        "comment_items": comment_items,
        "author_comment_items": author_comment_items,
        "author_comments": author_comments,
    }
    _TEXT_SOURCE_CACHE.pop(url, None)
    _TEXT_SOURCE_CACHE[url] = (result, time.time())
    if len(_TEXT_SOURCE_CACHE) > _MAX_CACHE_SIZE:
        _TEXT_SOURCE_CACHE.popitem(last=False)
    return result
    
# youtube 영상 title 가져오기
def get_youtube_video_title(video_id: str) -> str:
    url = f"{YOUTUBE_API_BASE}/videos"
    params = {
        "part": "snippet",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }

    res = requests.get(url, params=params).json()
    items = res.get("items", [])

    return items[0]["snippet"]["title"] if items else None

def get_youtube_playlist_title(playlist_id: str) -> str:
    url = f"{YOUTUBE_API_BASE}/playlists"
    params = {
        "part": "snippet",
        "id": playlist_id,
        "key": YOUTUBE_API_KEY,
    }

    res = requests.get(url, params=params).json()
    items = res.get("items", [])

    return items[0]["snippet"]["title"] if items else None

# 유튜브 플리 제목 가져오기
def get_video_title(video_id: str) -> str:
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

    return items[0]["snippet"].get("title", "").strip()

# 플리 제목 조회 
def get_playlist_title(playlist_id: str) -> str:
    payload = _youtube_get(
        "playlists",
        {
            "part": "snippet",
            "id": playlist_id,
        },
    )

    items = payload.get("items", [])
    if not items:
        return ""

    return items[0]["snippet"].get("title", "").strip()


_MUSIC_SECTION_SUBTITLES = {"곡", "song", "songs", "music", "음악", "노래", "트랙", "track", "tracks"}


def _is_music_section_subtitle(subtitle: str) -> bool:
    lowered = (subtitle or "").lower().strip()
    return any(kw in lowered for kw in _MUSIC_SECTION_SUBTITLES)


def _extract_cards_from_hcl(hcl: dict) -> list[dict]:
    songs = []
    for card in hcl.get("cards", []):
        # 구조 1: videoAttributeViewModel (구버전)
        vm = card.get("videoAttributeViewModel", {})
        title = (vm.get("title") or "").strip()
        artist = (vm.get("subtitle") or "").strip()
        album = ((vm.get("secondarySubtitle") or {}).get("content") or "").strip()

        # 구조 2: musicAttributeViewModel (신버전 대응)
        if not title:
            mv = card.get("musicAttributeViewModel") or card.get("musicCardAttributeViewModel", {})
            title = (mv.get("title") or "").strip()
            artist = (mv.get("artist") or mv.get("subtitle") or "").strip()
            album = (mv.get("album") or "").strip()

        if title and artist:
            songs.append({"title": title, "artist": artist, "album": album})
    return songs


def get_video_music_section(video_id: str) -> list[dict]:
    """YouTube InnerTube API로 영상의 '음악' 섹션(Content ID 매칭) 추출.
    반환: [{"title": ..., "artist": ..., "album": ...}, ...]
    음악 섹션이 없으면 빈 리스트.
    """
    try:
        resp = requests.post(
            f"{_INNERTUBE_BASE}/next",
            json={"videoId": video_id, "context": {"client": _INNERTUBE_CLIENT}},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except requests.RequestException:
        return []

    try:
        panels = data.get("engagementPanels", [])
        for panel in panels:
            renderer = (
                panel.get("engagementPanelSectionListRenderer")
                or panel.get("engagementPanelSectionListRendererV2")
                or {}
            )
            if renderer.get("panelIdentifier") != "engagement-panel-structured-description":
                continue

            content = renderer.get("content", {})
            # content 아래 structuredDescriptionContentRenderer 또는 직접 items
            desc_renderer = (
                content.get("structuredDescriptionContentRenderer")
                or content.get("engagementPanelSectionListRenderer", {}).get("content", {}).get("structuredDescriptionContentRenderer")
                or {}
            )
            items = desc_renderer.get("items") or []

            for item in items:
                hcl = item.get("horizontalCardListRenderer", {})
                if not hcl:
                    continue

                # subtitle 추출: richListHeaderRenderer 또는 simpleText 직접
                header = hcl.get("header", {})
                rich_header = header.get("richListHeaderRenderer", {})
                subtitle = (
                    (rich_header.get("subtitle") or {}).get("simpleText")
                    or (rich_header.get("title") or {}).get("simpleText")
                    or (header.get("titleText") or {}).get("runs", [{}])[0].get("text")
                    or ""
                )

                if not _is_music_section_subtitle(subtitle):
                    continue

                songs = _extract_cards_from_hcl(hcl)
                if songs:
                    return songs
    except (KeyError, TypeError, IndexError):
        pass

    return []
