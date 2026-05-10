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
