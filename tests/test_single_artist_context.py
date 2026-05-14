import unittest
from unittest.mock import patch

from app.parsers.song_parser import normalize_song_candidates
from app.services.pipeline_service import run_youtube_text_pipeline


class SingleArtistContextTests(unittest.TestCase):
    def test_normalize_song_candidates_fills_missing_artist_from_context(self):
        result = normalize_song_candidates(
            {"songs": [{"artist": "", "title": "Celebrity"}]},
            inferred_artist="IU",
        )

        self.assertEqual(result["songs"][0]["artist"], "IU")
        self.assertEqual(result["songs"][0]["title"], "Celebrity")
        self.assertTrue(result["songs"][0]["artist_inferred"])
        self.assertTrue(result["songs"][0]["is_complete"])

    @patch("app.services.pipeline_service.analyze_comments_prioritized")
    @patch("app.services.pipeline_service.analyze_description")
    @patch("app.services.pipeline_service.collect_text_sources")
    def test_title_based_single_artist_context_reaches_description_analysis(
        self,
        collect_mock,
        analyze_description_mock,
        analyze_comments_mock,
    ):
        collect_mock.return_value = {
            "input_url": "https://youtu.be/test",
            "video_id": "test",
            "youtube_title": "IU playlist",
            "description": "1. Celebrity",
            "comments": [],
            "comment_items": [],
        }
        analyze_description_mock.return_value = {
            "success": True,
            "songs": [
                {
                    "artist": "IU",
                    "title": "Celebrity",
                    "artist_inferred": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                }
            ],
            "signals": {},
            "metrics": {"song_count": 1, "complete_song_count": 1, "avg_completeness": 1.0},
            "failure_reason": "",
        }

        result = run_youtube_text_pipeline("https://youtu.be/test")

        analyze_description_mock.assert_called_once()
        self.assertEqual(analyze_description_mock.call_args.kwargs["inferred_artist"], "IU")
        analyze_comments_mock.assert_not_called()
        self.assertTrue(result["is_single_artist"])
        self.assertEqual(result["inferred_artist"], "IU")
        self.assertTrue(result["songs"][0]["artist_inferred"])

    @patch("app.services.pipeline_service.analyze_comments_prioritized")
    @patch("app.services.pipeline_service.analyze_description")
    @patch("app.services.pipeline_service.collect_text_sources")
    def test_extracted_song_majority_infers_single_artist(
        self,
        collect_mock,
        analyze_description_mock,
        analyze_comments_mock,
    ):
        collect_mock.return_value = {
            "input_url": "https://youtu.be/test",
            "video_id": "test",
            "youtube_title": "favorite playlist",
            "description": "",
            "comments": [],
            "comment_items": [],
        }
        analyze_description_mock.return_value = {
            "success": True,
            "songs": [
                {"artist": "IU", "title": "Good Day", "is_complete": True, "completeness_score": 1.0},
                {"artist": "IU", "title": "Palette", "is_complete": True, "completeness_score": 1.0},
                {"artist": "", "title": "Celebrity", "is_complete": False, "completeness_score": 0.5},
            ],
            "signals": {},
            "metrics": {"song_count": 3, "complete_song_count": 2, "avg_completeness": 0.833},
            "failure_reason": "",
        }

        result = run_youtube_text_pipeline("https://youtu.be/test")

        self.assertTrue(result["is_single_artist"])
        self.assertEqual(result["inferred_artist"], "IU")
        self.assertEqual(result["songs"][2]["artist"], "IU")
        self.assertTrue(result["songs"][2]["artist_inferred"])
        self.assertEqual(result["single_artist_detection"]["source"], "extracted_songs")
        analyze_comments_mock.assert_not_called()

    @patch(
        "app.services.pipeline_service.get_video_music_section",
        return_value=[
            {"artist": "Shawn Mendes", "title": "Treat You Better", "album": ""},
            {"artist": "Harry Styles", "title": "As It Was", "album": ""},
        ],
    )
    @patch("app.services.pipeline_service.analyze_comments_prioritized")
    @patch("app.services.pipeline_service.analyze_description")
    @patch("app.services.pipeline_service.collect_text_sources")
    def test_description_hashtag_single_artist_is_overridden_by_multi_artist_music_section(
        self,
        collect_mock,
        analyze_description_mock,
        analyze_comments_mock,
        music_section_mock,
    ):
        collect_mock.return_value = {
            "input_url": "https://youtu.be/test",
            "video_id": "test",
            "youtube_title": "favorite playlist",
            "description": "#cortis\n1. Treat You Better\n2. As It Was",
            "comments": [],
            "comment_items": [],
        }
        analyze_description_mock.return_value = {
            "success": True,
            "songs": [
                {
                    "artist": "cortis",
                    "title": "Treat You Better",
                    "artist_inferred": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
                {
                    "artist": "cortis",
                    "title": "As It Was",
                    "artist_inferred": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
            ],
            "signals": {},
            "metrics": {"song_count": 2, "complete_song_count": 2, "avg_completeness": 1.0},
            "failure_reason": "",
        }

        result = run_youtube_text_pipeline("https://youtu.be/test")

        self.assertFalse(result["is_single_artist"])
        self.assertEqual(result["single_artist_detection"]["source"], "music_section_multi_artist_override")
        self.assertEqual(result["songs"][0]["artist"], "Shawn Mendes")
        self.assertFalse(result["songs"][0]["artist_inferred"])
        self.assertTrue(result["songs"][0]["music_section_confirmed"])
        self.assertEqual(result["songs"][1]["artist"], "Harry Styles")
        analyze_comments_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
