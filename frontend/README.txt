실행 방법

1) 백엔드 실행
python -m uvicorn app.main:app --reload

2) CORS 확인
현재 main.py의 allow_origins는 3000만 허용 중입니다.
이 임시 UI를 VS Code Live Server(기본 5500)로 열면 막힐 수 있습니다.
테스트용으로 아래처럼 수정하세요.

allow_origins=[
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

또는 임시로 allow_origins=["*"]

3) 프론트 실행
index.html을 브라우저로 열거나 Live Server로 실행

4) 사용 순서
- Spotify 로그인 버튼 클릭
- 인증 완료 후 이 화면으로 돌아오기
- 유튜브 분석만 실행 또는 플레이리스트 생성

주의
현재 /spotify/callback은 프론트로 redirect하지 않고 JSON을 반환합니다.
그래서 인증 후 자동으로 원래 화면으로 돌아오지 않습니다.
이건 나중에 프론트 붙일 때 redirect 방식으로 개선하면 됩니다.
