# 2026 Paran Playlist AI - 현재 진행 상태

## 지금까지 구현한 범위

- **YouTube 입력 해석**
  - `watch?v=...` / `watch?v=...&list=RD...` / `playlist?list=...` / `youtu.be/...` 분기 처리
  - 잘못된 입력 형식은 400 에러로 반환
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

## 빠른 테스트 명령 (터미널)

```powershell
python -c "from backend.api.Youtube_API import collect_playlist_comments; from backend.api.OpenAI_API import extract_song_candidates_from_comments; import json; url='https://www.youtube.com/watch?v=jZcLQRWtv9Y'; y=collect_playlist_comments(url, max_videos=1, max_comments_per_video=30); r=extract_song_candidates_from_comments(y['comments'], comment_limit=30); print(json.dumps({'url': url, 'video_count': len(y['video_ids']), 'comment_count': len(y['comments']), 'songs': r['songs']}, ensure_ascii=False, indent=2))"
```
