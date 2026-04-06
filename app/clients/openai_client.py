from openai import OpenAI

from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

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


def extract_songs_with_llm(text_blocks: list[str]) -> str:
    joined_text = "\n\n".join(block.strip() for block in text_blocks if block and block.strip())

    if not joined_text:
        return '{"songs": []}'

    if not OPENAI_API_KEY:
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
