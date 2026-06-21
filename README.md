# 2026 Paran Playlist AI — OrangeBeats

YouTube 믹스/플레이리스트 영상의 비정형 텍스트를 LLM으로 분석해
Spotify 플레이리스트로 자동 변환하는 웹 서비스.

단순 텍스트 추출을 넘어, 텍스트 → OCR → ACR로 이어지는 3단계 Fallback 구조로
정보가 부족한 영상에서도 곡 정보를 추출하고, Spotify 매칭·플레이리스트 생성까지 연결한다.

---

## 핵심 기능

- **YouTube 입력 해석**
  - `watch?v=...` / `watch?v=...&list=RD...` / `playlist?list=...` / `youtu.be/...` 분기 처리
  - 영상/플레이리스트 자동 판별 및 `video_id` 추출
  - 잘못된 입력 형식은 400 에러로 반환

- **데이터 수집**
  - YouTube Data API `playlistItems`, `commentThreads` 호출
  - 설명란 + 댓글 + 음악 섹션(곡 제목/아티스트/앨범) 수집
  - 댓글 정책: 기본 30개, 최대 50개
  - 댓글 비활성화(403/404) 영상은 스킵 처리

- **3단계 Fallback 분석 구조**
  1. **Text Parsing** — 설명란·댓글 기반 1차 분석 (저비용·고속, 대부분 영상 처리)
  2. **Vision OCR** — 텍스트 부족 시 프레임 샘플링 후 화면 텍스트 인식 (`gpt-5.2` Vision)
  3. **ACRCloud** — 텍스트·화면 모두 부족 시 오디오 샘플 기반 음원 식별
  - 파이프라인에서 텍스트 추출 결과 품질을 평가해 Fallback 진입 여부 결정

- **LLM 추출 + 규칙 기반 검증**
  - LLM(`gpt-5.2`)으로 `artist/title` 후보 추출
  - LLM은 후보 추출 역할로 제한하고, parser·rule-based logic이 검증·정제·성공 판단 담당
  - `artist/title` swap 방지: 영상 전체 곡 목록의 패턴을 먼저 파악하는 global direction 로직 + rule 투표 + `swap_guard`
  - 환각 통제: "추측 금지" 프롬프트 + JSON 출력 제약 + NON_MUSIC 필터 (URL, 이메일, 소셜 핸들, 이미지 출처, 섹션 키워드 제외)

- **파싱 모듈화**
  - 비정형 텍스트 → JSON 파싱 유틸 분리
  - 타임스탬프 패턴(`00:00`, `1:23`) + `Song - Artist` 패턴 처리
  - 번호 목록, 한·영 혼합 표기, 괄호 포함 제목, 번역 제목 처리 범위 확장
  - JSON 응답 정규화 / 중복 제거
  - 성공 판단: `artist_exists`, `title_exists`, `is_complete`, `completeness_score` 기반 구조 검증

- **Spotify 매칭**
  - 추출된 곡 리스트를 Spotify Search API로 검색
  - `track:곡명 artist:가수명` 형식 query 생성, title/artist 필드 분리 검색
  - scoring·ranking 기반 최적 후보 선택, confidence score 계산 (제목·아티스트 유사도, 길이 일치도)
  - alias / romanization 처리로 한·영 표기 차이, 로마자 표기 대응
  - 매칭완료 / 확인필요 / 매칭실패 상태 분류 및 실패 사유 표시
  - Rate Limit(429) 대응: `Retry-After` 처리, 검색 결과 캐싱, Throttling, `ThreadPoolExecutor` 병렬 검색

- **플레이리스트 생성**
  - 사용자 후보 확인·선택 후 Spotify API로 플레이리스트 생성
  - 선택 트랙 추가, YouTube 썸네일을 커버로 활용
  - 매칭된 곡이 없으면 플레이리스트 생성 방지

---

외부 연동: OpenAI API · Spotify Web API · YouTube Data API · ACRCloud

---

## 공통 파라미터

- `MIN_TIMESTAMP`, `MIN_PATTERN`, `MIN_TRACKS`
- `COMMENT_LIMIT_DEFAULT`, `COMMENT_LIMIT_MAX`
- `AUDIO_SAMPLE_SEC_MIN` / `AUDIO_SAMPLE_SEC_MAX`
- `SPOTIFY_HIGH_CONF` / `SPOTIFY_MID_CONF`

---

## 성능 (실험 로그 기준, 총 497곡)

| 지표 | 결과 | 목표 |
|------|------|------|
| Extraction Rate (추출률) | 99.4% | 80% 이상 |
| Spotify Match Rate (매칭률) | 88.5% | 80% 이상 |
| Playlist Add Rate (추가율) | 89.9% | 70% 이상 |
| Final Success Rate (성공률) | 87.2% | 70% 이상 |
| Processing Time (영상 1개) | 10초 이내 | 10초 이내 |

---

## 빠른 테스트 명령 (터미널)

```powershell
python -c "from backend.api.Youtube_API import collect_playlist_comments; from backend.api.OpenAI_API import extract_song_candidates_from_comments; import json; url='https://www.youtube.com/watch?v=jZcLQRWtv9Y'; y=collect_playlist_comments(url, max_videos=1, max_comments_per_video=30); r=extract_song_candidates_from_comments(y['comments'], comment_limit=30); print(json.dumps({'url': url, 'video_count': len(y['video_ids']), 'comment_count': len(y['comments']), 'songs': r['songs']}, ensure_ascii=False, indent=2))"
```

---

## 기술 스택

- **Frontend**: React (반응형 웹)
- **Backend**: Python (FastAPI 계열 API 서버)
- **AI / 분석**: OpenAI `gpt-5.2` (Text / Vision), ACRCloud (Audio Fingerprinting)
- **음악 연동**: Spotify Web API (OAuth 2.0)
- **데이터**: YouTube Data API

---

## 팀

**오렌지캬라멜** — 이지민 · 이서연 · 양규림
2026 아주대학교 파란학기제
