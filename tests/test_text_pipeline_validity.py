import unittest
from unittest.mock import patch

from app.services.text_analysis import analyze_comments_prioritized, analyze_text_block


class TextPipelineValidityTests(unittest.TestCase):
    @patch("app.services.text_analysis.extract_songs_with_llm", return_value='{"songs":[]}')
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "low", "reason": ""},
    )
    def test_two_timestamped_songs_are_partial_but_valid(self, _direction_mock, _llm_mock):
        result = analyze_text_block(
            "\n".join(
                [
                    "00:00 IU - Good Day",
                    "03:30 NewJeans - Ditto",
                ]
            ),
            stage="description",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["is_partial_but_valid"])
        self.assertEqual(result["validity_reason"], "timestamp_pattern_detected")
        self.assertEqual(result["method"], "rule_based")
        _llm_mock.assert_not_called()

    @patch("app.services.text_analysis.extract_songs_with_llm", return_value='{"songs":[]}')
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "low", "reason": ""},
    )
    def test_bulleted_timestamp_tracklist_uses_rule_fast_path(self, _direction_mock, _llm_mock):
        result = analyze_text_block(
            "\n".join(
                [
                    "- 3:47 BoA - Atlantis Princess",
                    "- 7:05 BoA - Milky Way",
                    "- 11:03 SMTOWN - Hot Mail",
                ]
            ),
            stage="description",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "rule_based")
        _llm_mock.assert_not_called()

    @patch(
        "app.services.text_analysis.extract_songs_with_llm",
        return_value='{"songs":[{"artist":"Mitski","title":"My Love Mine All Mine"},{"artist":"d4vd","title":"Here With Me"}]}',
    )
    def test_general_text_uses_llm_before_rule_success(self, _llm_mock):
        result = analyze_text_block(
            "\n".join(
                [
                    "Mitski - My Love Mine All Mine",
                    "d4vd - Here With Me",
                ]
            ),
            stage="description",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "llm")
        _llm_mock.assert_called_once()

    @patch(
        "app.services.text_analysis.extract_songs_with_llm",
        return_value='{"songs":[{"artist":"Mitski","title":"My Love Mine All Mine"},{"artist":"d4vd","title":"Here With Me"},{"artist":"IU","title":"Good Day"}]}',
    )
    def test_strong_delimiter_text_still_uses_llm_first(self, _llm_mock):
        result = analyze_text_block(
            "\n".join(
                [
                    "Mitski - My Love Mine All Mine",
                    "d4vd - Here With Me",
                    "IU - Good Day",
                ]
            ),
            stage="description",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "llm")
        _llm_mock.assert_called_once()

    @patch("app.services.text_analysis.extract_songs_with_llm", return_value='{"songs":[]}')
    def test_noisy_comments_are_classified_without_extracting_songs(self, _llm_mock):
        comments = ["great video!!", "love this", "ㅋㅋㅋㅋ", "thanks"] * 4

        result = analyze_comments_prioritized(comments)

        self.assertFalse(result["success"])
        self.assertEqual(result["failure_reason"], "noisy_comments")
        self.assertEqual(result["source_priority_used"], "expanded_comments")

    @patch("app.services.text_analysis.extract_songs_with_llm", return_value='{"songs":[]}')
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "low", "reason": ""},
    )
    def test_timestamp_comment_is_used_before_expanded_comments(self, _direction_mock, _llm_mock):
        comments = [
            {"text": "nice", "like_count": 100},
            {"text": "so good", "like_count": 50},
            {"text": "thanks", "like_count": 40},
            {"text": "love this", "like_count": 30},
            {"text": "00:00 IU - Good Day\n03:30 NewJeans - Ditto", "like_count": 1},
        ]

        result = analyze_comments_prioritized(comments)

        self.assertTrue(result["success"])
        self.assertEqual(result["source_priority_used"], "timestamp_comments")


if __name__ == "__main__":
    unittest.main()
