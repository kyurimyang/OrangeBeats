# 2026 Paran Playlist AI - 현재 진행 상태

## 지금까지 구현된 범위

- **YouTube 입력 해석**
  - `watch?v=...` / `watch?v=...&list=RD...` / `playlist?list=...` / `youtu.be/...` 분기 처리
  - 잘못된 입력 형식은 400 에러로 명확히 반환
- **댓글 수집**
  - YouTube Data API `playlistItems`, `commentThreads` 호출
  - 댓글 정책: 기본 30개, 최대 50개
  - 댓글 비활성화(403/404) 영상은 스킵 처리
- **LLM 추출**
  - 댓글 텍스트를 LLM(`gpt-5.2`)에 전달해 `artist/title` JSON 추출
  - `max_results`는 기본 제한 없음 (`None`)
- **파싱 모듈화**
  - 비정형 텍스트 -> JSON 파싱 유틸 분리
  - 타임스탬프 패턴(`00:00`, `1:23`) + `Song - Artist` 패턴 처리
  - JSON 응답 정규화/중복 제거
- **공통 파라미터 파일**
  - `MIN_TIMESTAMP`, `MIN_PATTERN`, `MIN_TRACKS`
  - `COMMENT_LIMIT_DEFAULT`, `COMMENT_LIMIT_MAX`
  - `AUDIO_SAMPLE_SEC_MIN/MAX`, `SPOTIFY_HIGH_CONF/MID_CONF`

## 아직 미구현

- **STEP 1 설명란 분석** 실제 수집/추출 로직
- **STEP 3 OCR 분석** (프레임 추출/텍스트 인식)
- **STEP 4 오디오 인식(ACRCloud)** 연동
- **STEP 5 Spotify 매칭/플레이리스트 생성**
- FastAPI 라우트에서 단계별 조기 종료(`확정 곡 >= 3`) 오케스트레이션

## 현재 핵심 파일

- `backend/api/Youtube_API.py`
  - URL 타입 판별, playlist/video 댓글 수집
- `backend/api/OpenAI_API.py`
  - 댓글 -> LLM -> 곡 후보 JSON
- `backend/api/Parser_Utils.py`
  - 비정형 파싱/정규화/신호량 계산
- `backend/Pipeline_Paramas.py`
  - 파이프라인 공통 파라미터 상수
- `backend/main.py`
  - 기본 서버 헬스체크만 존재 (`/`, `/health`)

## 현재 파이프라인 상태 (실제 동작 기준)

1. YouTube URL/ID 입력
2. 댓글 수집 (기본 30, 최대 50)
3. LLM으로 가수/제목 JSON 추출
4. 파싱 정규화


