# OPENAI 호출
# 설명란/댓글 텍스트를 GPT에 보내고 응답 받기

from openai import OpenAI

from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

## parser가 처리하는 것 제외 보수적 규칙 수정
## few-shot prompting 
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
3. artist와 title이 둘 다 어느 정도 식별 가능한 경우만 포함한다.
4. 곡 정보가 아닌 일반 문장, 링크, 안내문, 플랫폼명 등은 포함하지 않는다.
5. "Artist - Title" 형식뿐 아니라 "Title - Artist" 형식도 처리한다.
6. 한 줄에 여러 곡이 있으면 구분 가능한 경우 각각 분리한다.
7. 설명, 마크다운, 코드블록 없이 JSON 객체만 반환한다.
8. 추출 결과가 없으면 아래처럼 반환한다.
9. 타임스탬프와 함께 나열된 줄(예: 00:12 Artist - Title, 01:20 Title - Artist)은
트랙리스트일 가능성이 높으므로 우선적으로 판단한다.
10. 댓글/설명란 안에 일반 문장과 곡 목록이 섞여 있더라도,
곡 목록으로 보이는 줄만 골라서 추출한다.

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
Lost in Static
Things I Never Said
Blue Light On The Desk

출력:
{
  "songs": []
}

예시 4
입력:
Pinned comment
00:00 JVKE - golden hour
02:31 Sufjan Stevens - Mystery of Love
너무 좋네요 감사합니다

출력:
{
  "songs": [
    {"artist": "JVKE", "title": "golden hour"},
    {"artist": "Sufjan Stevens", "title": "Mystery of Love"}
  ]
}

"""


 #LLM에 텍스트 묶음을 보내 곡 정보 JSON 문자열 반환
def extract_songs_with_llm(text_blocks: list[str]) -> str:
    joined_text = "\n\n".join(
        block.strip() for block in text_blocks if block and block.strip()
    )

    if not joined_text:
        return '{"songs": []}'

    try:
        response = client.chat.completions.create(
            model="gpt-5.2-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": joined_text},
            ],
        )

        content = response.choices[0].message.content
        return content if content else '{"songs": []}'

    except Exception:
        return '{"songs": []}'