import os

from dotenv import load_dotenv
from fastapi import HTTPException
from openai import OpenAI
from backend.constants.Pipeline_Paramas import COMMENT_LIMIT_DEFAULT, COMMENT_LIMIT_MAX
from backend.api.Parser_Utils import normalize_song_candidates, parse_json_from_text

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _build_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=OPENAI_API_KEY)


def extract_song_candidates_from_comments(
    comments: list[str],
    max_results: int | None = None,
    comment_limit: int = COMMENT_LIMIT_DEFAULT,
) -> dict:
    """
    댓글 목록을 LLM에 입력해서 {songs:[{artist,title}]} 형태로 반환한다.
    """
    if not comments:
        return {"songs": []}

    # LLM 입력 정책: 기본 30, 필요 시 최대 50 댓글까지 사용
    safe_comment_limit = max(1, min(comment_limit, COMMENT_LIMIT_MAX))
    safe_comment_count = min(len(comments), safe_comment_limit)

    comment_block = "\n".join(f"- {c.strip()}" for c in comments[:safe_comment_count] if c.strip())
    if not comment_block:
        return {"songs": []}

    client = _build_client()
    limit_instruction = (
        f"최대 {max_results}개.\n" if isinstance(max_results, int) and max_results > 0 else ""
    )
    response = client.chat.completions.create(
        model="gpt-5.2",
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
                    f"아래 댓글에서 가수/곡명을 추출해줘. {limit_instruction}"
                    '출력 형식: {"songs":[{"artist":"...","title":"..."}]}\n\n'
                    f"댓글:\n{comment_block}"
                ),
            },
        ],
    )

    raw_text = response.choices[0].message.content or ""
    try:
        parsed = parse_json_from_text(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return normalize_song_candidates(parsed)

