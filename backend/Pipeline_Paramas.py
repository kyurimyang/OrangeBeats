"""
전체 파이프라인에서 공통으로 사용하는 기준값 모음.
설명란 -> 댓글 -> OCR -> 오디오 -> Spotify 흐름에서 단계별 판단에 사용한다.
"""

# 단계 종료 기준
MIN_TRACKS = 3

# 설명란/댓글 텍스트 신호 기준
MIN_TIMESTAMP = 3
MIN_PATTERN = 2

# 댓글 수집/LLM 입력 범위
COMMENT_LIMIT_DEFAULT = 30
COMMENT_LIMIT_MAX = 50

# 오디오 샘플링 (ACRCloud)
AUDIO_SAMPLE_SEC_MIN = 12
AUDIO_SAMPLE_SEC_MAX = 15

# Spotify 매칭 신뢰도 기준
SPOTIFY_HIGH_CONF = 0.85
SPOTIFY_MID_CONF = 0.65
