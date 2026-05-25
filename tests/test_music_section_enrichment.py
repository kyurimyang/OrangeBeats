import unittest
from unittest.mock import patch

from app.services.pipeline_service import (
    _apply_single_artist_context,
    _enrich_songs_with_music_section,
    _titles_match,
)
from app.services.text_analysis import _annotate_song_evidence


class MusicSectionEnrichmentTests(unittest.TestCase):
    def test_single_artist_context_does_not_override_strong_timestamp_pair_artist(self):
        result = _apply_single_artist_context(
            {
                "songs": [
                    {
                        "artist": "KiiiKiii",
                        "title": "Dancing Alone",
                        "raw_line": "03:16 KiiiKiii - Dancing Alone",
                        "evidence_type": "timestamp_pair",
                        "confidence": "high",
                        "artist_inferred": False,
                        "artist_exists": True,
                        "title_exists": True,
                        "is_complete": True,
                        "completeness_score": 1.0,
                    }
                ],
                "metrics": {},
            },
            {"is_single_artist": True, "inferred_artist": "NewJeans", "source": "title_description"},
        )

        self.assertEqual(result["songs"][0]["artist"], "KiiiKiii")
        self.assertFalse(result["songs"][0]["artist_inferred"])

    def test_title_only_timestamp_annotation_restores_full_title_from_raw_line(self):
        songs = _annotate_song_evidence(
            [
                {
                    "artist": "HoMe",
                    "title": "boy",
                    "raw_line": "00:56 HoMe boy",
                    "evidence_type": "timestamp_pair",
                }
            ],
            source_text="00:56 HoMe boy",
            source_name="comments",
            method="llm",
        )

        self.assertEqual(songs[0]["artist"], "HoMe boy")
        self.assertEqual(songs[0]["title"], "HoMe boy")
        self.assertEqual(songs[0]["evidence_type"], "title_only_timestamp")
        self.assertTrue(songs[0]["timestamp_title_normalized"])

    def test_llm_raw_line_outside_source_recovers_to_matching_timestamp_line(self):
        songs = _annotate_song_evidence(
            [
                {
                    "artist": "a sad night",
                    "title": "track을 아시네 ㅋㅋㅋ 지리노",
                    "raw_line": "a sad night track을 아시네 ㅋㅋㅋ 지리노",
                }
            ],
            source_text="25:22 a sad night track",
            source_name="comments",
            method="llm",
        )

        self.assertEqual(songs[0]["artist"], "a sad night track")
        self.assertEqual(songs[0]["title"], "a sad night track")
        self.assertEqual(songs[0]["raw_line"], "25:22 a sad night track")

    def test_short_english_substrings_do_not_match_music_section_titles(self):
        self.assertFalse(_titles_match("XI", "Xii"))
        self.assertFalse(_titles_match("boy", "HoMe boy (Feat. LeeHi)"))

    @patch("app.services.pipeline_service.get_video_music_section")
    def test_title_only_timestamp_uses_matching_music_section_artist(self, mock_music):
        mock_music.return_value = [
            {"title": "Xii", "artist": "CODE KUNST", "album": "PEOPLE"},
        ]

        songs, extras = _enrich_songs_with_music_section(
            [
                {
                    "title": "Xii",
                    "artist": "Xii",
                    "raw_line": "00:01 Xii",
                    "evidence_type": "title_only_timestamp",
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                }
            ],
            "video-id",
        )

        self.assertEqual(extras, [])
        self.assertEqual(songs[0]["title"], "Xii")
        self.assertEqual(songs[0]["artist"], "CODE KUNST")
        self.assertEqual(songs[0]["album"], "PEOPLE")
        self.assertEqual(songs[0]["original_text_artist"], "Xii")
        self.assertTrue(songs[0]["music_section_confirmed"])

    @patch("app.services.pipeline_service.get_video_music_section")
    def test_title_only_timestamp_uses_ordered_music_section_when_alias_does_not_match(self, mock_music):
        mock_music.return_value = [
            {"title": "Xii", "artist": "CODE KUNST", "album": "PEOPLE"},
            {"title": "What is Love?", "artist": "LEEHI", "album": "4 ONLY"},
        ]

        songs, _extras = _enrich_songs_with_music_section(
            [
                {
                    "title": "Xii",
                    "artist": "Xii",
                    "raw_line": "00:01 Xii",
                    "evidence_type": "title_only_timestamp",
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
                {
                    "title": "어려워",
                    "artist": "어려워",
                    "raw_line": "12:18 어려워",
                    "evidence_type": "title_only_timestamp",
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
            ],
            "video-id",
        )

        self.assertEqual(songs[1]["title"], "What is Love?")
        self.assertEqual(songs[1]["artist"], "LEEHI")
        self.assertEqual(songs[1]["original_text_title"], "어려워")
        self.assertEqual(songs[1]["music_section_confirmed"], "positional_suggestion")

    @patch("app.services.pipeline_service.get_video_music_section")
    def test_strong_timestamp_pair_keeps_artist_when_music_section_has_multiple_artists(self, mock_music):
        mock_music.return_value = [
            {"title": "Bubble Gum", "artist": "NewJeans", "album": ""},
            {"title": "Mermaid", "artist": "GFRIEND", "album": ""},
        ]

        songs, _extras = _enrich_songs_with_music_section(
            [
                {
                    "title": "Bubble Gum",
                    "artist": "NewJeans",
                    "raw_line": "00:00 NewJeans - Bubble Gum",
                    "evidence_type": "timestamp_pair",
                    "confidence": "high",
                    "artist_inferred": False,
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
                {
                    "title": "LOVE",
                    "artist": "STAYC",
                    "raw_line": "06:32 STAYC - LOVE",
                    "evidence_type": "timestamp_pair",
                    "confidence": "high",
                    "artist_inferred": True,
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
                {
                    "title": "Mermaid",
                    "artist": "여자친구",
                    "raw_line": "16:19 여자친구 - Mermaid",
                    "evidence_type": "timestamp_pair",
                    "confidence": "high",
                    "artist_inferred": False,
                    "artist_exists": True,
                    "title_exists": True,
                    "is_complete": True,
                    "completeness_score": 1.0,
                },
            ],
            "video-id",
        )

        self.assertEqual(songs[1]["artist"], "STAYC")
        self.assertTrue(songs[1]["artist_exists"])


if __name__ == "__main__":
    unittest.main()
