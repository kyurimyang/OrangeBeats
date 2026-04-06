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
    "tracklist", "music", "song list", "추천곡", "문의", "contact", "timeline", "time line"
]

NATURAL_SENTENCE_HINTS = [
    "오늘", "이번", "추천", "감사", "사랑", "응원", "즐감", "좋아요", "구독",
    "please", "hope", "thanks", "enjoy", "subscribe", "comment", "watch"
]

TITLE_DELIMITERS = [" - ", " – ", " — ", " | ", " : ", " ~ "]

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
    r"^\s*provided to youtube by.*",
]
