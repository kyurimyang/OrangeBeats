from openai import OpenAI

from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """
너는 유튜브 설명란/댓글에서 음악 정보를 추출하는 도우미다.
반드시 JSON만 반환해라.
형식:
{
  "songs": [
    {"artist": "가수명", "title": "곡명"}
  ]
}

규칙:
- 없는 정보를 추측하지 마라.
- 확실하지 않으면 제외해라.
- 같은 곡은 중복 포함하지 마라.
- 설명란/댓글에 없는 곡은 절대 만들지 마라.
"""


def extract_songs_with_llm(text_blocks: list[str]) -> str:
    joined_text = "\n\n".join([block for block in text_blocks if block and block.strip()])

    if not joined_text.strip():
        return '{"songs": []}'

    response = client.chat.completions.create(
        model="gpt-5.2",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": joined_text},
        ],
    )

    return response.choices[0].message.content or '{"songs": []}'