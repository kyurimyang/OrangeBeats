from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI is not None) else None

SYSTEM_PROMPT = """
너는 YouTube 설명란/댓글 텍스트에서 음악 곡 정보를 추출하는 AI다.
반드시 아래 형식의 JSON 객체만 반환해라.

{
  "songs": [
    {"artist": "가수명", "title": "곡명"}
  ]
}

규칙:
1. 입력 텍스트에 근거해서만 추출한다.
2. 추측하거나 없는 정보를 만들지 않는다.
3. artist와 title이 둘 다 식별 가능한 경우만 포함한다.
4. 곡 정보가 아닌 일반 문장, 링크, 안내문, 플랫폼명, 감상문, timeline/tracklist 헤더는 포함하지 않는다.
5. 타임스탬프는 제거하고 곡 정보만 남긴다.
6. "Artist - Title" 형식이면 artist=왼쪽, title=오른쪽이다.
7. "Title - Artist" 형식이면 title=왼쪽, artist=오른쪽이다.
8. "가수 ~ 제목" 형식도 구분자(~)를 제거해서 해석한다.
9. JSON의 artist 필드에는 반드시 가수명/아티스트명만 넣는다.
10. JSON의 title 필드에는 반드시 곡 제목만 넣는다.
11. "로꼬 & 펀치", "HIGH4, 아이유"처럼 여러 아티스트가 함께 적혀 있으면 하나의 artist 문자열로 유지한다. 분리하지 않는다.
12. artist와 title의 위치가 불명확하면 더 자연스러운 쪽을 택하되, 확신이 없으면 제외한다.
13. 설명, 마크다운, 코드블록 없이 JSON 객체만 반환한다.
14. 추출 결과가 없으면 아래처럼 반환한다.

{
  "songs": []
}

예시 1
입력:
00:12 Taylor Swift - Lover
00:45 SZA - Snooze

출력:
{
  "songs": [
    {"artist": "Taylor Swift", "title": "Lover"},
    {"artist": "SZA", "title": "Snooze"}
  ]
}

예시 2
입력:
00:21 Lover - Taylor Swift
01:10 Snooze - SZA

출력:
{
  "songs": [
    {"artist": "Taylor Swift", "title": "Lover"},
    {"artist": "SZA", "title": "Snooze"}
  ]
}

예시 3
입력:
*timeline
[0:00] 마틴스미스 - 봄 그리고 너
[3:51] 악뮤 - Be With You

출력:
{
  "songs": [
    {"artist": "마틴스미스", "title": "봄 그리고 너"},
    {"artist": "악뮤", "title": "Be With You"}
  ]
}

예시 4
입력:
00:00 HIGH4, 아이유 - 봄 사랑 벚꽃 말고
00:00 로꼬 & 펀치 - Say Yes

출력:
{
  "songs": [
    {"artist": "HIGH4, 아이유", "title": "봄 사랑 벚꽃 말고"},
    {"artist": "로꼬 & 펀치", "title": "Say Yes"}
  ]
}
"""

SPOTIFY_RERANK_SYSTEM_PROMPT = """
너는 음악 매칭 검증 AI다.
역할은 사용자가 추출한 곡 정보(artist/title)와 Spotify 검색 후보 3~5개를 비교해서
가장 맞는 후보를 고르는 것이다.

반드시 아래 JSON만 반환해라.

{
  "picked_index": 0,
  "confidence": "high",
  "should_swap": false,
  "reason": "짧은 이유"
}

규칙:
1. picked_index는 후보 목록의 index를 의미한다. 맞는 후보가 없으면 -1을 반환한다.
2. should_swap은 사용자의 입력 artist/title이 뒤집힌 것으로 보이면 true, 아니면 false다.
3. title과 artist를 모두 본다. title만 비슷하고 artist가 다르면 신중하게 판단한다.
4. 후보 중 어느 것도 확실하지 않으면 picked_index=-1로 반환한다.
5. confidence는 high / medium / low 중 하나만 사용한다.
6. 설명문 없이 JSON만 반환한다.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None

    return None


def extract_songs_with_llm(text_blocks: List[str]) -> str:
    joined_text = "\n\n".join(block.strip() for block in text_blocks if block and block.strip())

    if not joined_text:
        return '{"songs": []}'

    if not OPENAI_API_KEY or client is None:
        print("OPENAI_API_KEY가 없습니다.")
        return '{"songs": []}'

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": joined_text},
            ],
        )

        content = response.choices[0].message.content
        print("LLM raw response =", content)
        return content if content else '{"songs": []}'

    except Exception as e:
        print("OpenAI 호출 오류 =", str(e))
        return '{"songs": []}'


def rerank_spotify_candidates_with_llm(
    input_artist: str,
    input_title: str,
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    candidates 예시:
    [
      {
        "index": 0,
        "name": "...",
        "artists": ["..."],
        "score": 0.88,
        "orientation": "original"
      }
    ]
    """
    if not OPENAI_API_KEY or client is None:
        return None

    if not candidates:
        return None

    payload = {
        "input_song": {
            "artist": input_artist or "",
            "title": input_title or "",
        },
        "candidates": candidates,
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SPOTIFY_RERANK_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
        )

        content = response.choices[0].message.content or ""
        print("Spotify rerank LLM raw =", content)

        parsed = _extract_json_object(content)
        if not parsed:
            return None

        picked_index = parsed.get("picked_index", -1)
        confidence = str(parsed.get("confidence", "low")).lower().strip()
        should_swap = bool(parsed.get("should_swap", False))
        reason = str(parsed.get("reason", "")).strip()

        if not isinstance(picked_index, int):
            return None

        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        return {
            "picked_index": picked_index,
            "confidence": confidence,
            "should_swap": should_swap,
            "reason": reason,
        }

    except Exception as e:
        print("Spotify rerank LLM 오류 =", str(e))
        return None