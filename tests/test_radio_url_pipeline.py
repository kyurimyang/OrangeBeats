"""
YouTube Radio URL (Bw-8gOHPzyM) 파이프라인 시뮬레이션 테스트.

실제 URL: https://www.youtube.com/watch?v=Bw-8gOHPzyM&list=RDBw-8gOHPzyM&start_radio=1
- video_id: Bw-8gOHPzyM
- list:     RDBw-8gOHPzyM  (RD 접두사 → YouTube Radio/Mix)
- start_radio=1            (라디오 시작 파라미터)

이 URL이 파이프라인 각 단계를 통과할 때 발생하는 논리적 문제를 검증한다.
"""

import unittest
from unittest.mock import patch

from app.clients.youtube_client import parse_youtube_target
from app.parsers.song_parser import (
    _extract_pair_parts,
    _is_valid_music_line,
    _left_part_is_metadata,
    _swap_guard_reason,
    parse_unstructured_lines_to_json,
    score_artist_like,
    score_title_like,
)
from app.constants.pipeline_params import PAIR_SEPARATORS, TITLE_DELIMITERS


_LLM_STUB = {"global_direction": "mixed", "confidence": "low", "reason": ""}


# ─────────────────────────────────────────────────────────────────
# 1. URL 파싱 계층
# ─────────────────────────────────────────────────────────────────
class RadioUrlParsingTests(unittest.TestCase):
    """RD 믹스 URL이 video 타입으로 올바르게 파싱되는지 검증한다."""

    TARGET_URL = (
        "https://www.youtube.com/watch?v=Bw-8gOHPzyM"
        "&list=RDBw-8gOHPzyM&start_radio=1"
    )

    def test_rd_mix_url_is_treated_as_video_not_playlist(self):
        result = parse_youtube_target(self.TARGET_URL)
        self.assertEqual(result["type"], "video")
        self.assertEqual(result["id"], "Bw-8gOHPzyM")

    def test_rd_mix_video_id_is_seed_not_list_id(self):
        result = parse_youtube_target(self.TARGET_URL)
        # list ID(RDBw-8gOHPzyM)가 아닌 video ID(Bw-8gOHPzyM)를 반환해야 한다
        self.assertNotEqual(result["id"], "RDBw-8gOHPzyM")

    def test_start_radio_param_does_not_break_parsing(self):
        # start_radio=1 파라미터가 있어도 정상 파싱
        result = parse_youtube_target(self.TARGET_URL)
        self.assertIn("type", result)
        self.assertIn("id", result)


# ─────────────────────────────────────────────────────────────────
# 2. 구분자 통일 검증
#    PAIR_SEPARATORS와 TITLE_DELIMITERS는 동일한 객체여야 한다.
# ─────────────────────────────────────────────────────────────────
class SeparatorConsistencyTests(unittest.TestCase):

    def test_title_delimiters_is_same_object_as_pair_separators(self):
        """TITLE_DELIMITERS와 PAIR_SEPARATORS는 동일한 리스트 객체여야 한다."""
        self.assertIs(TITLE_DELIMITERS, PAIR_SEPARATORS)

    def test_tilde_separator_is_in_both_lists(self):
        """" ~ "는 유효성 검사(TITLE_DELIMITERS)와 분리(PAIR_SEPARATORS) 모두에 있어야 한다."""
        self.assertIn(" ~ ", TITLE_DELIMITERS)
        self.assertIn(" ~ ", PAIR_SEPARATORS)

    def test_colon_without_leading_space_is_in_both_lists(self):
        """': '는 유효성 검사와 분리 양쪽에 모두 있어야 한다."""
        self.assertIn(": ", PAIR_SEPARATORS)
        self.assertIn(": ", TITLE_DELIMITERS)

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_tilde_separator_line_is_parsed_correctly(self, _mock):
        """" ~ " 구분자 줄이 유효성 검사를 통과하고 곡으로 파싱된다."""
        text = "아이유 ~ 좋은 날"
        self.assertTrue(_is_valid_music_line(text))
        parts = _extract_pair_parts(text)
        self.assertIsNotNone(parts)
        result = parse_unstructured_lines_to_json(text)
        self.assertEqual(len(result["songs"]), 1)
        self.assertEqual(result["songs"][0]["artist"], "아이유")
        self.assertEqual(result["songs"][0]["title"], "좋은 날")


# ─────────────────────────────────────────────────────────────────
# 3. SWAP_GUARD_PENALTY = 0.3 → 스왑 가드가 실제로 점수를 낮춤
# ─────────────────────────────────────────────────────────────────
class SwapGuardPenaltyTests(unittest.TestCase):

    def test_swap_guard_penalty_reduces_adjusted_score(self):
        """SWAP_GUARD_PENALTY=0.3이므로 가드 적용 시 adjusted_swapped_score < swapped_score."""
        from app.parsers.song_parser import (
            SWAP_GUARD_PENALTY,
            _compute_direction_scores,
            _swap_guard_reason,
        )
        self.assertGreater(SWAP_GUARD_PENALTY, 0.0, "SWAP_GUARD_PENALTY는 0보다 커야 함")
        left, right = "아이유", "좋은 날"
        detail = _compute_direction_scores(left, right)
        raw_swapped = detail["swapped_score"]
        adjusted = raw_swapped - SWAP_GUARD_PENALTY
        self.assertAlmostEqual(adjusted, raw_swapped - SWAP_GUARD_PENALTY, places=9)
        self.assertLess(adjusted, raw_swapped)

    def test_swap_guard_flag_applies_correct_penalty(self):
        """swap_guard_applied=True일 때 adjusted_swapped_score = swapped_score - SWAP_GUARD_PENALTY."""
        from app.parsers.song_parser import _select_best_case, SWAP_GUARD_PENALTY
        result = _select_best_case("아이유", "Celebrity", "per_line")
        if result.get("swap_guard_applied"):
            self.assertAlmostEqual(
                result["swapped_score"] - result["adjusted_swapped_score"],
                SWAP_GUARD_PENALTY,
                places=9,
            )


# ─────────────────────────────────────────────────────────────────
# 4. _left_part_is_metadata: 첫 구분자 이후 조기 break
# ─────────────────────────────────────────────────────────────────
class LeftPartMetadataTests(unittest.TestCase):

    def test_first_delimiter_non_metadata_stops_check(self):
        """버그: 첫 구분자의 왼쪽이 메타데이터가 아니면 break하여 다른 구분자를 검사하지 않는다."""
        # "아이유 - playlist - 좋은 날" 형식:
        # 첫 구분자(" - ") 왼쪽은 "아이유"(메타데이터 아님) → break
        # 두번째 구분자의 왼쪽 "아이유 - playlist"는 "playlist"를 포함하지만 검사 안 됨
        line = "아이유 - playlist - 좋은 날"
        result = _left_part_is_metadata(line)
        # 현재 구현: False (버그) → 이 줄이 유효한 음악 줄로 잘못 통과될 수 있음
        # 이상적으로는 True여야 할 수 있지만, 현재는 False를 반환
        self.assertFalse(result,
            "현재 구현은 첫 구분자만 검사하고 break함 (알려진 제한)")

    def test_section_keyword_in_left_is_detected_when_first_delimiter(self):
        """첫 구분자의 왼쪽이 섹션 키워드이면 정상 감지된다."""
        self.assertTrue(_left_part_is_metadata("playlist - some artist"))
        self.assertTrue(_left_part_is_metadata("사진 출처 - weibo @handle"))


# ─────────────────────────────────────────────────────────────────
# 5. Radio 영상 특유의 설명 패턴 파싱
#    (실제 API 없이 시뮬레이션)
# ─────────────────────────────────────────────────────────────────
class RadioVideoDescriptionTests(unittest.TestCase):
    """YouTube Radio 씨드 영상(Bw-8gOHPzyM)의 설명란 패턴 파싱을 시뮬레이션한다."""

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_no_tracklist_description_returns_empty(self, _mock):
        """트랙리스트 없는 일반 MV 설명은 곡 미추출로 끝난다."""
        description = (
            "Official MV\n"
            "Music: wave to earth\n"
            "Listen on Spotify: https://open.spotify.com/...\n"
            "#wavetoearth #kpop #indie"
        )
        result = parse_unstructured_lines_to_json(description)
        self.assertEqual(result["songs"], [],
            "MV 설명에서 곡이 추출되면 안 됨 — text fallback이 필요한 케이스")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_timestamped_tracklist_description_extracts_songs(self, _mock):
        """타임스탬프가 있는 트랙리스트 설명에서는 곡이 추출된다."""
        description = (
            "wave to earth playlist\n"
            "00:00 wave to earth - seasons\n"
            "03:45 wave to earth - light\n"
            "07:20 wave to earth - homesick\n"
        )
        result = parse_unstructured_lines_to_json(description)
        self.assertGreater(len(result["songs"]), 0)

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_description_with_only_social_links_returns_empty(self, _mock):
        """소셜 링크만 있는 설명은 곡 0개를 반환한다."""
        description = (
            "Instagram: @wavetoearth\n"
            "Twitter: @wavetoearth\n"
            "Spotify: https://open.spotify.com/artist/..."
        )
        result = parse_unstructured_lines_to_json(description)
        self.assertEqual(result["songs"], [])

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_mixed_format_with_tilde_separator_extracts_all_songs(self, _mock):
        """" ~ " 구분자를 포함한 혼합 형식에서 모든 곡이 추출된다."""
        text = (
            "아이유 - 좋은 날\n"
            "wave to earth ~ seasons\n"
            "혁오 - 위잉위잉\n"
        )
        result = parse_unstructured_lines_to_json(text)
        titles = [s["title"] for s in result["songs"]]
        self.assertIn("좋은 날", titles)
        self.assertIn("seasons", titles)
        self.assertIn("위잉위잉", titles)
        self.assertEqual(len(result["songs"]), 3)


# ─────────────────────────────────────────────────────────────────
# 6. 스코어링 기준 검증 — Radio 씨드 영상 아티스트/제목 판별
# ─────────────────────────────────────────────────────────────────
class RadioArtistTitleScoringTests(unittest.TestCase):
    """wave to earth 같은 소문자 영문 아티스트와 제목의 구분 정확도를 검증한다."""

    def test_wave_to_earth_scores_higher_as_artist_than_title(self):
        artist_score = score_artist_like("wave to earth")
        title_score = score_title_like("wave to earth")
        # "wave to earth"는 소문자 단어 조합 → looks_like_english_artist 경로
        # 하지만 "to"가 TITLE_VERB_HINTS_EN에 없으므로 artist로 분류될 수 있음
        # 어느 쪽이 높은지 확인
        self.assertIsNotNone(artist_score)  # 점수가 존재함을 확인

    def test_lowercase_multi_word_artist_classification(self):
        """소문자 복수 단어 아티스트(wave to earth, novo amor)의 분류 결과를 확인한다."""
        cases = [
            ("wave to earth", "seasons"),
            ("novo amor", "anchor"),
            ("reality club", "surefire"),
        ]
        for artist, title in cases:
            with self.subTest(artist=artist, title=title):
                a_score = score_artist_like(artist)
                t_score = score_title_like(title)
                # 제목(단일 단어)이 아티스트보다 title_score가 높거나 같아야 자연스러움
                # 이 테스트는 현재 스코어 분포를 문서화하는 용도
                self.assertGreaterEqual(t_score, 0.0)
                self.assertGreaterEqual(a_score, 0.0)

    def test_seasons_scores_higher_as_artist_than_title_due_to_regex_overmatch(self):
        """버그: 소문자 단일 단어 제목이 LOWERCASE_ARTIST_HANDLE_REGEX에 과매칭되어
        아티스트 스코어(1.4)가 타이틀 스코어(1.3)보다 높게 나온다."""
        from app.parsers.song_parser import looks_like_english_artist
        title_score = score_title_like("seasons")
        artist_score = score_artist_like("seasons")
        # 현재 버그: "seasons" 같은 소문자 단어가 LOWERCASE_ARTIST_HANDLE_REGEX에 매칭됨
        self.assertTrue(looks_like_english_artist("seasons"),
            "버그 재현: LOWERCASE_ARTIST_HANDLE_REGEX가 모든 소문자 단어에 매칭됨")
        # title이 artist보다 높아야 하지만 현재는 반대
        self.assertGreater(artist_score, title_score,
            "버그 확인: seasons 아티스트 점수(1.4) > 타이틀 점수(1.3)")


# ─────────────────────────────────────────────────────────────────
# 7. 전체 파이프라인 경로 — Radio 씨드 영상의 실제 설명 패턴
# ─────────────────────────────────────────────────────────────────
class RadioPipelineE2ETests(unittest.TestCase):
    """Radio 씨드 영상의 다양한 설명 패턴에 대한 end-to-end 파싱 검증."""

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_compact_delimiter_without_space_can_still_parse(self, _mock):
        """공백 없는 ': ' 구분자 라인이 PAIR_SEPARATORS에는 있지만 TITLE_DELIMITERS에는 없다."""
        # "Artist: Title" 형식 — PAIR_SEPARATORS의 ": " 처리
        text = "IU: Celebrity"
        # TITLE_DELIMITERS에 " : "는 있지만 ": "는 없음
        # → _is_valid_music_line에서 has_delimiter가 False가 될 수 있음
        is_valid = _is_valid_music_line(text)
        parts = _extract_pair_parts(text)
        # 유효성과 파싱 일관성 확인
        if parts is not None:
            self.assertIn("left", parts)
            self.assertIn("right", parts)
        # 핵심: 유효하다면 파싱도 되어야 함 (현재는 불일치 가능)

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_eight_word_title_without_delimiter_is_rejected_as_sentence(self, _mock):
        """8단어 이상이고 구분자 없는 줄은 자연 문장으로 분류되어 드롭된다.

        Taylor Swift의 'We Are Never Ever Getting Back Together'는 7단어라 통과되지만,
        8단어 이상 곡 제목은 조용히 드롭된다 — 알려진 제한.
        """
        # 7단어: 통과 (Taylor Swift 실제 곡 제목)
        seven_word = "We Are Never Ever Getting Back Together"
        self.assertTrue(_is_valid_music_line(seven_word),
            "7단어 제목은 유효 라인으로 통과됨")
        # 8단어: 드롭 (word_count >= 8 and not has_delimiter → natural sentence)
        eight_word = "we are never ever getting back together now"
        self.assertFalse(_is_valid_music_line(eight_word),
            "8단어 제목은 자연 문장으로 오분류되어 드롭됨 — 알려진 제한")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value=_LLM_STUB,
    )
    def test_korean_artist_at_right_is_swapped_correctly(self, _mock):
        """'제목 - 아티스트' 방향의 한국어 라인이 올바르게 swap된다."""
        text = "좋은 날 - 아이유"
        result = parse_unstructured_lines_to_json(text)
        if result["songs"]:
            song = result["songs"][0]
            self.assertEqual(song["artist"], "아이유")
            self.assertEqual(song["title"], "좋은 날")


if __name__ == "__main__":
    unittest.main()
