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
]

NATURAL_SENTENCE_HINTS = [
    "오늘", "이번", "추천", "감사", "사랑", "응원", "즐감", "좋아요", "구독",
    "please", "hope", "thanks", "enjoy", "subscribe", "comment", "watch"
]

TITLE_DELIMITERS = [" - ", " – ", " — ", " | ", " : ", " ~ ", " / "]

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
    # Photo/image credit lines
    r"사진\s*출처",
    r"이미지\s*출처",
    r"photo\s*(?:credit|source|by)\b",
    r"image\s*(?:credit|source|by)\b",
    # Social media handles without email domain (e.g. "Weibo @鞠婧祎")
    r"@[\w가-힣一-鿿぀-ヿ]+\s*$",
    # Lines made of mathematical/decorative Unicode (styled YouTube headers like 𝑷𝒍𝒂𝒚𝒍𝒊𝒔𝒕)
    r"[\U0001D400-\U0001D7FF]",
]

PAIR_SEPARATORS = [
    " - ",
    " – ",
    " — ",
    " | ",
    " / ",
    " : ",
    ": ",
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

CORE_ARTIST_ALIAS_MAP = {
    "아이콘": ["iKON"],
    "지드래곤": ["G-DRAGON", "GD"],
    "방탄소년단": ["BTS"],
    "백현": ["BAEKHYUN"],
    "엔하이픈": ["ENHYPEN"],
    "블락비": ["Block B"],
    "엑소": ["EXO"],
    "악뮤": ["AKMU", "Akdong Musician"],
    "소녀시대": ["Girls' Generation", "Girls Generation", "SNSD"],
    "아이유": ["IU"],
    "예린백": ["Yerin Baek"],
    "태연": ["TAEYEON"],
    "윤상": ["Yoon Sang"],
    "롤러코스터": ["Roller Coaster", "RollerCoaster"],
    "클래지콰이": ["Clazziquai", "Clazziquai Project"],
}

CORE_ARTIST_ALIAS_MAP.update({
    "백예린": ["Yerin Baek"],
    "원슈타인": ["Wonstein"],
    "MC몽": ["MC Mong"],
    "휘성": ["Wheesung", "Realslow"],
    "윤하": ["Younha"],
    "나윤권": ["Na Yoon Kwon", "Nayoon Kwon"],
    "팀": ["Tim"],
    "씨야": ["SeeYa", "Kim Yeonji", "Kim Yeon Ji"],
    "더윈": ["The Wind"],
})

CORE_TITLE_ALIAS_MAP = {
    "놀이공원": ["Amusement Park"],
    "바래다줄게": ["Take You Home"],
    "우산": ["Love Song"],
    "취향저격": ["MY TYPE"],
    "오늘따라": ["TODAY"],
    "사랑의 인사": ["Lovely Sweet Heart"],
}
