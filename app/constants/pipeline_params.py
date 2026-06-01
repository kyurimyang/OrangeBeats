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
    "조유리": ["JO YURI", "Jo Yuri"],
    "최예나": ["YENA", "Choi Yena", "Choi Ye Na"],
    "드림캐쳐": ["Dreamcatcher"],
    "코르티스": ["CORTIS"],
    "올데이 프로젝트": ["ALLDAY PROJECT"],
    "올데이프로젝트": ["ALLDAY PROJECT"],
    "캣츠아이": ["KATSEYE"],
    "미야오": ["MEOVV"],
    "베이비몬스터": ["BABYMONSTER"],
    "베몬": ["BABYMONSTER"],
    # 한국 힙합/아이돌 한영 병기
    "에픽하이": ["Epik High"],
    "다이나믹듀오": ["Dynamic Duo", "Dynamicduo"],
    "원타임": ["1TYM"],
    "리쌍": ["LeeSSang", "리쌍 (LeeSSang)"],
    "슈프림팀": ["Supreme Team"],
    "싸이": ["PSY"],
    "이효리": ["Lee Hyori"],
    "선미": ["SUNMI"],
    "브라운아이드걸스": ["Brown Eyed Girls"],
    "화사": ["Hwasa", "HWASA"],
    "윤미래": ["Yoonmirae", "T"],
    # 4세대 아이돌 (Spotify 영문명으로만 검색됨)
    "뉴진스": ["NewJeans"],
    "르세라핌": ["LE SSERAFIM"],
    "스트레이키즈": ["Stray Kids"],
    "에이티즈": ["ATEEZ"],
    "있지": ["ITZY"],
    "오마이걸": ["OH MY GIRL"],
    "에버글로우": ["EVERGLOW"],
    "케플러": ["Kep1er"],
    "아이브": ["IVE"],
    "엔믹스": ["NMIXX"],
    "케이시": ["Kassy"],
    "위아이": ["WEi"],
    "퀸덤퍼즐": ["Queendom Puzzle"],
    # 발라드/가요 (로마자 표기 혼용)
    "박효신": ["Park Hyo Shin", "Park Hyoshin"],
    "이선희": ["Lee Sun Hee", "Lee Sunhee"],
    "임재범": ["Lim Jae Beom", "Im Jaebeom"],
    "김범수": ["Kim Bum Soo", "Kim Bumsoo"],
    "케이윌": ["K.Will", "K Will"],
    "포맨": ["4MEN"],
    "나얼": ["Naul"],
    "이적": ["Lee Juck"],
    "빅마마": ["Big Mama", "BIGMAMA"],
    "버즈": ["Buzz"],
    "god": ["G.O.D"],
    "노을": ["Noel"],
    "박완규": ["Park Wan Kyu"],
    "신승훈": ["Shin Seung Hun"],
    "조성모": ["Jo Sung Mo"],
    # 대소문자 표기 혼용 아티스트
    "샤이니": ["SHINee", "Shinee", "SHINEE"],
    "빅뱅": ["BIGBANG", "Big Bang"],
    "투피엠": ["2PM"],
    "투에이엠": ["2AM"],
    "씨엔블루": ["CNBLUE", "CN Blue"],
    "에프티아일랜드": ["FTIsland", "FTISLAND", "FT Island"],
})

CORE_TITLE_ALIAS_MAP = {
    "놀이공원": ["Amusement Park"],
    "바래다줄게": ["Take You Home"],
    "우산": ["Love Song"],
    "취향저격": ["MY TYPE"],
    "오늘따라": ["TODAY"],
    "사랑의 인사": ["Lovely Sweet Heart"],
    "내가 제일 잘 나가": ["I Am The Best"],
    # Spotify에 영문 제목으로만 등록된 한국어 명곡
    "봄날": ["Spring Day"],
    "밤편지": ["Through the Night"],
    "좋은 날": ["Good Day"],
    "팔레트": ["Palette"],
    "에잇": ["eight"],
    "eight": ["에잇"],
    "사랑이 잘": ["Can You See My Heart"],
    "어디에도": ["Nowhere"],
    "홀씨": ["Dandelion"],
    "칠월 칠일": ["Milky Way"],
    "동화": ["Fairy Tale"],
}
