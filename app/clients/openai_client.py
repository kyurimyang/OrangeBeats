from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from app.config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI is not None) else None

SYSTEM_PROMPT = """
너는 YouTube 설명란/댓글 텍스트에서 음악 곡 정보를 추출하는 AI다.
반드시 아래 형식의 JSON 객체만 반환해라.

{
  "songs": [
    {
      "artist": "artist name",
      "title": "song title",
      "raw_line": "exact source line from the input",
      "confidence": "high",
      "evidence_type": "timestamp_pair"
    }
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
13. Include raw_line for every extracted song. raw_line must be an exact line or sentence that appears in the input.
14. Include confidence as high, medium, or low. Use high only when the source line directly contains the track evidence.
15. Include evidence_type as timestamp_pair, delimiter_pair, title_only_timestamp, explicit_tracklist, or other.
16. If there is no exact raw_line evidence, do not extract the song.
17. Return only the JSON object, without markdown, comments, or code fences.
18. If there are no extraction results, return this:

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

예시 5
입력:
00:00 404(new era) - kiikii
00:30 777 - kiikii

출력:
{
  "songs": [
    {"artist": "kiikii", "title": "404(new era)"},
    {"artist": "kiikii", "title": "777"}
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

DIRECTION_DETECT_SYSTEM_PROMPT = """
You are an AI that determines the overall notation direction of a YouTube music track list.
Return only a JSON object. Do not include markdown or any explanation outside JSON.

Your task is not to match individual songs. Only decide the global direction used by the list.
Track lists from the same YouTube video usually repeat one format consistently.

Return exactly this schema:
{
  "global_direction": "artist_title" | "title_artist" | "mixed",
  "confidence": "high" | "medium" | "low",
  "reason": "short reason"
}

Rules:
1. artist_title means most left values are artists and most right values are titles.
2. title_artist means most left values are titles and most right values are artists.
3. mixed means the direction is mixed or cannot be confidently decided.
4. Do not identify or validate individual songs; judge the whole list pattern.
5. If feat., ft., or with appears inside parentheses on the left, the left side is likely a title.
6. If the right side repeatedly looks like person/artist names across many lines, title_artist is likely.
7. If the left side repeatedly looks like person/artist names across many lines, artist_title is likely.
8. If confidence is low, return mixed with confidence low.
9. JSON only.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _supports_custom_temperature(model: str) -> bool:
    normalized = (model or "").lower().strip()
    return not normalized.startswith(("gpt-5", "o1", "o3", "o4"))


def _is_temperature_unsupported_error(error: Exception) -> bool:
    message = str(error).lower()
    return "temperature" in message and "unsupported" in message


def _create_chat_completion(messages: List[Dict[str, str]]):
    kwargs = {
        "model": OPENAI_MODEL,
        "messages": messages,
    }

    if _supports_custom_temperature(OPENAI_MODEL):
        kwargs["temperature"] = 0

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        if "temperature" in kwargs and _is_temperature_unsupported_error(exc):
            kwargs.pop("temperature", None)
            return client.chat.completions.create(**kwargs)
        raise


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
        response = _create_chat_completion(
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


def detect_direction_with_llm(pairs: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    if not OPENAI_API_KEY or client is None:
        print("[direction-llm] skipped: OpenAI client unavailable")
        return None

    cleaned_pairs = []
    for pair in pairs[:40]:
        if not isinstance(pair, dict):
            continue
        left = str(pair.get("left") or "").strip()
        right = str(pair.get("right") or "").strip()
        if left and right:
            cleaned_pairs.append({"left": left, "right": right})

    if not cleaned_pairs:
        return None

    payload = {"pairs": cleaned_pairs}

    try:
        response = _create_chat_completion(
            messages=[
                {"role": "system", "content": DIRECTION_DETECT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
        )

        content = response.choices[0].message.content or ""
        print("[direction-llm] raw =", content)

        parsed = _extract_json_object(content)
        if not parsed:
            print("[direction-llm] invalid_json")
            return None

        direction = str(parsed.get("global_direction") or "mixed").lower().strip()
        confidence = str(parsed.get("confidence") or "low").lower().strip()
        reason = str(parsed.get("reason") or "").strip()

        if direction not in {"artist_title", "title_artist", "mixed"}:
            direction = "mixed"
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        result = {
            "global_direction": direction,
            "confidence": confidence,
            "reason": reason,
        }
        print(
            f"[direction-llm] global_direction={direction} "
            f"confidence={confidence} reason='{reason}'"
        )
        return result

    except Exception as e:
        print("[direction-llm] error =", str(e))
        return None


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
        response = _create_chat_completion(
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

