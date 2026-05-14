# Handoff: orangebeats — Youtube → 스트리밍 Playlist 변환 서비스

## Overview
**orangebeats**는 Youtube 영상 / 플레이리스트 URL을 입력하면 AI가 트랙리스트를 추출해 Spotify(또는 다른 스트리밍 서비스)에 동일한 플레이리스트를 자동 생성해주는 웹 서비스입니다.

이 번들은 5개의 핵심 화면 + FAQ + Pricing으로 구성된 클릭형 프로토타입입니다.

## About the Design Files
**중요**: 이 번들 안의 HTML 파일들은 **디자인 레퍼런스**입니다 — 의도된 외관과 인터랙션을 보여주는 프로토타입이지, 그대로 배포할 코드가 아니에요.

작업의 목표는 이 HTML 디자인을 **타겟 코드베이스의 환경 (Next.js / React / Vue 등) 에 맞게 재구현**하는 것입니다. 코드베이스에 이미 정의된 디자인 시스템·컴포넌트 라이브러리·라우팅 패턴을 따라 다시 작성해주세요. 코드베이스가 아직 없다면, 프로젝트에 가장 적합한 프레임워크(권장: **Next.js 14 App Router + Tailwind CSS**)를 선택해 구현하세요.

## Fidelity
**High-fidelity (hifi)** — 최종 컬러·타이포그래피·스페이싱·인터랙션이 모두 결정되어 있습니다. 색상값, 폰트 크기, radius, 그라데이션 등을 **그대로** 재현해주세요. 단, 코드 구조는 코드베이스의 관습을 따르면 됩니다.

---

## Screens / Views

### 01. Landing (홈)
- **Purpose**: 서비스 소개 + 즉시 URL 입력 가능. CTA는 "Analyze".
- **Layout**: max-width 1280px, 중앙 정렬. 풀-스크롤 페이지.
  - Hero: 상단 padding 96px, 중앙정렬 타이포그래피
  - "How it works" 3-step grid (3-column)
  - Featured playlists 5-column grid
  - Big CTA section (12-column grid, 7:5 비율)
  - Footer
- **Hero 타이포**:
  - H1: 104px / Pretendard / 500 weight / line-height 0.95 / letter-spacing -0.04em
  - "Youtube Playlist를 ㅡ / 링크 한번에 내 **스트리밍**으로." (orange→mint gradient text on "스트리밍")
- **URL Input**:
  - 너비 760px, 높이 72px, 28px gradient border (orange→mint)
  - 내부 배경 #0d0d0d, 좌측 Youtube 아이콘(#FD6D11), 우측 "Analyze" 버튼 (orange gradient, 56px height)
- **Trust dots row**: "무료 · 회원가입 필요 없음" / "분당 24,800곡 매칭" / "OCR/ACR fallback 포함" — 12px text-white/40

### 02. URL Input (`/url`)
- **Purpose**: 더 명확한 URL 입력 + 플레이리스트 제목 모드 선택.
- **Layout**: max-width 1080px 중앙 정렬, 헤드라인 → URL 입력 → 제목 옵션 2개 (2-col grid) → breadcrumb.
- **Title Mode 카드**:
  - 옵션 A: "유튜브 제목 그대로 사용" — 라디오 + 영상 제목 미리보기
  - 옵션 B: "직접 제목 입력" — 라디오 + 인라인 텍스트 입력
- **Validation**: URL이 `youtu.be` 또는 `youtube.com` 포함 시에만 활성. 에러 시 입력창 border가 빨강 그라데이션으로 변경.

### 03. Loading / Analyzing (`/loading`)
- **Purpose**: 진행 상황 시각화. 4 stage 자동 진행 후 candidates로 이동.
- **Stages** (총 약 6.6초):
  1. `fetch` — 영상 정보 불러오기 (1.4s)
  2. `trans` — 자막·설명 분석 (1.8s)
  3. `match` — 곡 매칭 (2.2s)
  4. `tidy` — 결과 정리 (1.2s)
- **Visual**: 중앙 270px 회전 비닐 + 오렌지 글로우, 하단 progress bar (orange→mint gradient + shimmer), stage 4개 카드 (완료시 mint, 진행중 orange).
- **취소** 버튼: URL 화면으로 복귀.

### 04. Candidate Matching (`/candidates`)
- **Purpose**: 추출된 트랙리스트 검토 — 후보 교체 / 제외 / OCR·ACR fallback.
- **Layout**:
  - 헤더 좌측: 타이틀 + 설명. 우측: stat 카드 3개 (포함곡수 / 높은 신뢰 / 총 길이)
  - 원본 영상 카드 (썸네일 + 메타 + Youtube 열기 버튼)
  - 트랙 리스트 (테이블형, 행 8개)
  - 하단: "원하는 노래가 없어요" (좌) / "이대로 Playlist 만들기" (우)
- **Track row 컬럼**:
  - `#` (font-mono 12px) · 커버(48px) + extracted→title · ConfidencePill + meter bar (140px) · duration · 토글 액션 (▼ 후보 / × 제외)
- **ConfidencePill 4 레벨**:
  - `high` — mint (#5EEAD4) "높은 일치율"
  - `similar` — peach (#FFB07A) "비슷한 곡 발견"
  - `live` — yellow (#F1C40F) "라이브 버전 가능성"
  - `alt` — violet (#A78BFA) "다른 버전 추천"
- **Alt candidates**: 행 expand 시 2-col grid로 후보 카드 표시. 클릭하면 메인 트랙 교체.
- **ACR Modal**: 모달 오픈 — OCR vs ACR 2-col 선택 → "실행하기" 클릭 시 loading으로 회귀.

### 05. Playlist Created (`/playlist`)
- **Purpose**: 변환 완료 + 실제 플레이리스트 미리보기 + 평점.
- **Layout**:
  - 성공 배지 (mint check) + 타이틀 "Playlist를 성공적으로 만들었어요!"
  - Hero 카드: 240px 그라데이션 커버 + 플레이리스트 메타 + CTA 3개 ("Spotify에서 바로 듣기" primary)
  - 2-col 그리드: 좌 8col 트랙 리스트, 우 4col 평점 카드 + 다음 액션 2개
- **Rating 카드**: 5개 별 (인터랙티브 hover) → 텍스트 영역 → "평가 보내기" → 제출 후 mint check + 감사 메시지
- **트랙 리스트**: hover 시 # → ▶ 아이콘 교체, 우측 좋아요 버튼 fade-in

### 06. FAQ (`/faq`)
- max-width 920px 1-col. 아코디언 6개. 아이템 클릭시 + → × 회전. 활성 아이템 orange border.

### 07. Pricing (`/pricing`)
- 3-col 카드 (Free / Pro / Studio). Pro는 "MOST POPULAR" 배지 + ob-glass 강조. 각 카드 feature 리스트 (체크 + 텍스트).

---

## Interactions & Behavior

### Navigation
- 5개 메인 플로우: landing → url → loading → candidates → playlist
- 하단 floating demo nav (dev용, production에선 제거)
- NavBar 좌측 로고 = home, 우측 메뉴 = FAQ / Pricing / Convert
- 모든 화면 진입 시 `scroll-to-top` 처리

### Animations
- 페이지 전환: `.ob-fade` — opacity 0→1, translateY 8px→0, 0.45s ease-out
- Loading: vinyl 회전 (10s linear infinite), progress shimmer, dots animation
- Equaliser bars: scaleY 0.25→1, 1.2s ease-in-out, stagger 0.15s
- Hover transitions: 모두 0.2s ease

### Forms & Validation
- URL: `/youtu(\.be|be\.com)/` 정규식 검증
- 별점: 0이면 평가 보내기 비활성

### State Management
**Per-screen state**:
- LandingScreen: `url` (input value)
- URLScreen: `url`, `titleMode` ('youtube'|'custom'), `customTitle`, `error`
- LoadingScreen: `stageIdx`, `pct` (requestAnimationFrame 기반)
- CandidatesScreen: `tracks[]` (kept toggle, swap), `expanded` (open alt panel), `showACR`
- PlaylistScreen: `rating`, `hoverRating`, `feedback`, `submitted`

**Global**:
- Current route + route state (selected URL, title)
- 디자인 토큰 (CSS custom properties)

### Real-world API hooks (implementation 시)
- `POST /api/extract` — { url } → { video, tracks[] }
- `POST /api/match`   — { tracks } → { matched[] with confidence }
- `POST /api/fallback` — { videoId, method:'ocr'|'acr' } → { tracks }
- `POST /api/spotify/create` — { title, tracks } → { playlistUrl }
- `POST /api/rate`    — { rating, feedback }

---

## Design Tokens

### Colors
```css
--ob-bg:       #0a0a0a   /* base dark */
--ob-ink-900:  #0a0a0a
--ob-ink-850:  #101010
--ob-ink-800:  #161616
--ob-ink-700:  #1f1f1f

--ob-orange:        #FD6D11   /* primary accent */
--ob-orange-soft:   #FFB07A
--ob-orange-deep:   #C24A00

--ob-mint:          #5EEAD4   /* secondary accent (success/streaming) */
--ob-mint-soft:     #A6F2E5
--ob-mint-deep:     #2BB8A3

--violet:           #A78BFA   /* alt confidence */
--yellow:           #F1C40F   /* live confidence */
--red-400:          #F87171   /* error */

/* text on dark */
text-white          /* primary */
text-white/85       /* emphasized body */
text-white/60       /* secondary */
text-white/45       /* tertiary */
text-white/30       /* placeholder */
```

### Typography
- **Display**: Pretendard Variable, 500 weight
  - 104px / 64px / 56px / 44px (hero levels)
  - letter-spacing: -0.03em ~ -0.04em
  - line-height: 0.95 ~ 1.05
- **Body**: Pretendard, 400/500
  - 17px (subhead), 15px (body), 14px (UI), 13px (small), 12px (caption)
- **Mono**: JetBrains Mono — 모든 eyebrow / meta / step counter
  - 11px / 10px, uppercase, letter-spacing 0.18em~0.2em

### Spacing
Tailwind 기본 scale 사용. 주요 컨테이너 padding:
- Section: `pt-24 pb-10` (96/40)
- Card large: `p-8` (32) ~ `p-12` (48)
- Card medium: `p-5` ~ `p-7`
- Component gap: `gap-3` (12), `gap-4` (16), `gap-5` (20)

### Border Radius
- Pill (button/input): `rounded-full` (9999)
- Card large: `28px` ~ `32px`
- Card medium: `16px` ~ `20px`
- Track row item: `12px`

### Shadows
- Primary button: `0 8px 24px -8px rgba(253,109,17,0.6)` + inset `0 1px 0 rgba(255,255,255,0.25)`
- Vinyl: `0 30px 60px -20px rgba(0,0,0,0.8)`
- Big cover: `0 30px 60px -20px rgba(253,109,17,0.6)`

### Effects
- `.ob-glass` — radial-gradient + linear-gradient overlay + 1px white/8 border + 20px blur
- `.ob-glass-soft` — 약한 linear-gradient + 1px white/6 border (no blur)
- `.ob-chip` — white/5 bg + 1px white/8 border
- `.ob-grad-accent` — text gradient (orange→peach→mint)

---

## Assets
- **이미지 자산 없음** — 모든 트랙 커버는 procedural CSS (`TrackCover` 컴포넌트가 seed 기반 그라데이션 + SVG 도형 생성)
- **아이콘**: 인라인 SVG, 1.8 stroke-width 표준. 모두 `ob-components.jsx`에 정의.
- **로고**: `BrandMark` 컴포넌트 — orange↔mint gradient circle + 검은 도넛홀 + 오렌지 점.

---

## Files in this bundle

| File | Purpose |
|---|---|
| `Orange Beats.html` | 메인 prototype 진입점 |
| `ob-components.jsx` | 공유 컴포넌트 (NavBar, BrandMark, Icons, TrackCover, ConfidencePill, Vinyl, Footer 등) |
| `ob-data.jsx` | 데모 데이터 (영상, 트랙, 후보, featured playlists) |
| `ob-screen-landing.jsx` | 01 Landing |
| `ob-screen-url.jsx` | 02 URL Input |
| `ob-screen-loading.jsx` | 03 Analyzing |
| `ob-screen-candidates.jsx` | 04 Candidate Matching + ACR Modal |
| `ob-screen-playlist.jsx` | 05 Playlist Created |
| `ob-screen-misc.jsx` | 06 FAQ + 07 Pricing |
| `ob-app.jsx` | 라우팅 + Tweaks 패널 |

---

## Implementation Guide for Claude Code

VS Code에서 Claude Code를 켜고 다음과 같이 요청하세요:

```
이 폴더의 design_handoff_orangebeats/ 안의 HTML/JSX 파일들은 디자인 레퍼런스입니다.
README.md를 먼저 읽고 디자인을 파악해주세요.

이걸 [Next.js 14 + Tailwind + TypeScript] 프로젝트로 재구현하고 싶습니다.
1) 디자인 토큰을 tailwind.config.ts에 등록
2) 각 화면을 app/[route]/page.tsx로 분리
3) 공유 컴포넌트는 components/ 안에 배치
4) 더미 데이터는 lib/demo-data.ts로 분리 (실제 API 연동은 추후)
5) 페이지 전환 애니메이션은 framer-motion 사용
```

또는 기존 프로젝트가 있다면:
```
기존 [your-stack] 프로젝트의 디자인 시스템 / 컴포넌트 라이브러리를 사용해서
design_handoff_orangebeats/ 안의 디자인을 그대로 재구현해주세요.
색상값과 spacing은 README의 토큰을 그대로 따라주세요.
```

### Recommended file structure (Next.js 예시)
```
app/
  page.tsx              # 01 Landing
  url/page.tsx          # 02
  analyzing/page.tsx    # 03
  candidates/page.tsx   # 04
  playlist/page.tsx     # 05
  faq/page.tsx
  pricing/page.tsx
components/
  brand-mark.tsx
  nav-bar.tsx
  track-cover.tsx
  confidence-pill.tsx
  vinyl.tsx
  equaliser-bars.tsx
  ui/
    button.tsx
    input.tsx
    glass-card.tsx
lib/
  demo-data.ts
  cn.ts
```
