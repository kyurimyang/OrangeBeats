import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _build_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _parse_json_from_text(raw_text: str) -> Any:
    text = raw_text.strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced[0].strip()

    candidates = [text]

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidates.append(text[obj_start : obj_end + 1])

    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidates.append(text[arr_start : arr_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError("LLM 응답에서 JSON 파싱에 실패했습니다.")


def _normalize_songs(data: Any) -> dict[str, list[dict[str, str]]]:
    songs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    raw_items: list[Any]
    if isinstance(data, dict) and isinstance(data.get("songs"), list):
        raw_items = data["songs"]
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        artist = str(item.get("artist", "unknown")).strip() or "unknown"
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        key = (artist.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        songs.append({"artist": artist, "title": title})

    return {"songs": songs}


def extract_song_candidates_from_comments(comments: list[str], max_results: int = 15) -> dict:
    """
    댓글 목록을 LLM에 입력해서 {songs:[{artist,title}]} 형태로 반환한다.
    """
    if not comments:
        return {"songs": []}

    comment_block = "\n".join(f"- {c.strip()}" for c in comments[:150] if c.strip())
    if not comment_block:
        return {"songs": []}

    client = _build_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 유튜브 댓글에서 노래 정보를 추출하는 도우미다. "
                    "반드시 JSON만 출력하고, songs 배열에는 artist/title만 넣어라. "
                    "확실하지 않은 항목은 제외하고 중복은 제거해라."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"아래 댓글에서 가수/곡명을 추출해줘. 최대 {max_results}개.\n"
                    '출력 형식: {"songs":[{"artist":"...","title":"..."}]}\n\n'
                    f"댓글:\n{comment_block}"
                ),
            },
        ],
    )

    raw_text = response.choices[0].message.content or ""
    try:
        parsed = _parse_json_from_text(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _normalize_songs(parsed)

