import unittest
from unittest.mock import patch

from app.parsers.song_parser import parse_unstructured_lines_to_json
from app.services.pipeline_service import _supplement_songs_from_candidates


class NumericParentheticalTracklistTests(unittest.TestCase):
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "mixed", "confidence": "low", "reason": ""},
    )
    def test_timestamped_numeric_parenthetical_title_is_kept(self, _direction_mock):
        result = parse_unstructured_lines_to_json("23:13 404 (new era) - kiiikiii")

        self.assertEqual(len(result["songs"]), 1)
        self.assertEqual(result["songs"][0]["artist"], "kiiikiii")
        self.assertEqual(result["songs"][0]["title"], "404 (new era)")
        self.assertEqual(result["songs"][0]["timestamp"], "23:13")

    def test_music_section_only_candidate_can_supplement_text_songs(self):
        songs = [{"artist": "red velvet", "title": "\ubd10 (look)", "music_section_confirmed": "positional"}]
        updated, candidates = _supplement_songs_from_candidates(
            songs,
            [{"artist": "KiiiKiii", "title": "404 (New Era)", "source": "music_section_only"}],
        )

        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[1]["source"], "music_section_only")
        self.assertEqual(updated[1]["confidence"], "low")
        self.assertEqual(updated[1]["review_reason"], "music_section_only_candidate")
        self.assertEqual(candidates[0]["merge_decision"], "added")
        self.assertEqual(candidates[0]["debug_reason"], "added_from_music_section_only_missing_from_text")

    def test_music_section_only_duplicate_is_excluded_with_reason(self):
        updated, candidates = _supplement_songs_from_candidates(
            [{"artist": "KiiiKiii", "title": "404 (new era)"}],
            [{"artist": "KiiiKiii", "title": "404 (New Era)", "source": "music_section_only"}],
        )

        self.assertEqual(len(updated), 1)
        self.assertEqual(candidates[0]["merge_decision"], "excluded")
        self.assertEqual(candidates[0]["debug_reason"], "duplicate_title_artist")


if __name__ == "__main__":
    unittest.main()
