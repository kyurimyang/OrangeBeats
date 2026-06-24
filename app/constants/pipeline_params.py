# 단계 종료 기준
MIN_SONG_COUNT = 3
MIN_COMPLETE_SONG_COUNT = 2
MIN_COMPLETENESS_RATIO = 0.6

# 설명란/댓글 텍스트 신호 기준
MIN_TIMESTAMP_COUNT = 3
MIN_PATTERN_COUNT = 2

# 댓글 수집/LLM 입력 범위
COMMENT_LIMIT_DEFAULT = 30
COMMENT_LIMIT_MAX = 50

# 오디오 샘플링 (ACRCloud)
AUDIO_SAMPLE_SEC_MIN = 12
AUDIO_SAMPLE_SEC_MAX = 15

# Spotify 매칭 신뢰도 기준
SPOTIFY_HIGH_CONF = 0.85
SPOTIFY_MID_CONF = 0.65

SECTION_KEYWORDS = [
    "축가", "행진", "입장", "퇴장", "bgm", "브금", "playlist", "setlist",
    "tracklist", "music", "song list", "추천곡", "문의", "contact", "timeline", "time line",
    "플레이리스트", "출처", "weibo", "사진 출처", "이미지 출처",
    "pinterest", "comment", "comments",
    "instagram", "twitter", "facebook", "tiktok", "tumblr",
    "photo", "image", "cover", "artwork", "thumbnail",
    # 광고·스킵·협찬 섹션 마커 (구분자 없는 라인에서만 차단)
    "광고", "스킵", "협찬", "스폰서", "광고구간", "광고시작", "광고끝",
    "인스타그램",
]

NATURAL_SENTENCE_HINTS = [
    "오늘", "이번", "추천", "감사", "사랑", "응원", "즐감", "좋아요", "구독",
    "please", "hope", "thanks", "enjoy", "subscribe", "comment", "watch"
]

PAIR_SEPARATORS = [
    " - ",
    " – ",
    " — ",
    " | ",
    " / ",
    " : ",
    ": ",
    " ~ ",
    " _ ",
]

# TITLE_DELIMITERS is an alias — validity checks and splitting share one list.
TITLE_DELIMITERS = PAIR_SEPARATORS

NON_MUSIC_LINE_PATTERNS = [
    r"https?://\S+",
    r"www\.\S+",
    r"\S+@\S+\.\S+",
    r"^\s*문의[:]?",
    r"^\s*contact[:]?",
    r"^\s*instagram[:]?",
    r"^\s*email[:]?",
    r"^\s*phone[:]?",
    r"^\s*thank you\b.*",
    r"^\s*listen on\b.*",
    r"^\s*available on\b.*",
    r"^\s*\*?timeline\b.*",
    r"^\s*time line\b.*",
    r"^\s*음원으로 인한 수익.*",
    r"^\s*수익은 발생하지 않습니다.*",
    r"^\s*all rights reserved.*",
    r"^\s*provided by\b.*",
    r"^\s*provided to youtube by.*",
    r"^\s*ost\s*[:|].*",
    r".*(?:문장|시집|수록된|수록되어).*(?:입니다|있구요|있고요).*$",
    r".*는\s*'.+\s[-–—]\s.+'$",
    r"^\s*(?:ig|insta|instagram|spotify|yt|youtube|tiktok|soundcloud)\s*[:|]\s*@?[\w\.\-]{2,}\s*$",
    # Photo/image credit lines
    r"사진\s*출처",
    r"이미지\s*출처",
    r"photo\s*(?:credit|source|by)\b",
    r"image\s*(?:credit|source|by)\b",
    # Social media handles without email domain (e.g. "Weibo @鞠婧祎")
    r"@[\w가-힣一-鿿぀-ヿ]+\s*$",
    # Lines made of mathematical/decorative Unicode (styled YouTube headers like 𝑷𝒍𝒂𝒚𝒍𝒊𝒔𝒕)
    r"[\U0001D400-\U0001D7FF]",
    # 한국어 안내/유도 문구
    r"^\s*[▶►▷]\s*구독",
    r"^\s*[▶►▷]\s*좋아요",
    r"^\s*[▶►▷]\s*알림",
    r"^\s*✔\s*저작권",
    r"^\s*📌",
    r"^\s*⬇",
    r"^\s*이\s*영상의\s*모든\s*(?:음악|노래|곡)",
    r"^\s*본\s*영상에\s*사용(?:된|되는|한)",
    r"^\s*저작권은\s*(?:해당|원)",
    r"^\s*(?:구독|좋아요|알림설정)\s*(?:눌러|부탁|해주)",
    r"^\s*(?:앨범|album)\s*[:：]\s*$",
    r"^\s*(?:track\s*list|트랙\s*리스트|tracklist)\s*$",
    r"^\s*(?:재생목록|플레이리스트)\s*[:：]?\s*$",
    r"^\s*(?:업로드|upload|posted)\s*(?:by|:)",
    r"^\s*제\s*\d+\s*(?:편|화|회)\s*$",
    # 광고·스폰서 명시 문구 (영어)
    r"^\s*sponsored?\s+by\b",
    r"^\s*this\s+(?:video|content)\s+(?:is|was)\s+(?:sponsored|brought\s+to\s+you)\b",
    r"^\s*in\s+(?:paid\s+)?partnership\s+with\b",
    r"^\s*thanks?\s+to\s+(?:our\s+)?sponsor",
    r"^\s*(?:ad|ads)\s*(?:break|start|end|here)?\s*$",
    r"^\s*skip\s+(?:intro|this|ad|ads|chapter|sponsor|me)\b",
    # 광고 건너뛰기 한국어 문구
    r"^\s*광고\s*(?:시작|끝|구간|스킵|건너뛰기|skip)\b",
    r"^\s*광고를?\s*건너뛰",
    r"^\s*(?:ppl|광고주|협찬사)\s*[:：]",
    r"^\s*협찬\s*[:：]",
]

GLOBAL_DIRECTION_SAMPLE_SIZE = 5
SWAP_SCORE_MARGIN = 0.14

MATCH_NOISE_KEYWORDS = [
    "official",
    "audio",
    "video",
    "lyrics",
    "lyric",
    "mv",
    "ost",
    "remix",
    "version",
    "ver",
    "remaster",
    "remastered",
    "prod",
    "produced",
]

import json as _json
from pathlib import Path as _Path

_ALIASES_PATH = _Path(__file__).parent / "aliases.json"
_aliases = _json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
CORE_ARTIST_ALIAS_MAP: dict[str, list[str]] = _aliases["artist"]
CORE_TITLE_ALIAS_MAP: dict[str, list[str]] = _aliases["title"]

