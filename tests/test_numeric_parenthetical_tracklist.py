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

    def test_music_section_translation_duplicate_same_artist_position_is_excluded(self):
        updated, candidates = _supplement_songs_from_candidates(
            [
                {
                    "artist": "\uc870\uc720\ub9ac",
                    "title": "\uc774\uc81c \uc548\ub155!",
                    "raw_line": "\uc870\uc720\ub9ac - \uc774\uc81c \uc548\ub155!",
                    "evidence_type": "delimiter_pair",
                    "confidence": "high",
                },
                {
                    "artist": "\ucd5c\uc608\ub098",
                    "title": "\uadf8\uac74 \uc0ac\ub791\uc774\uc5c8\ub2e4\uace0",
                    "raw_line": "\ucd5c\uc608\ub098 - \uadf8\uac74 \uc0ac\ub791\uc774\uc5c8\ub2e4\uace0",
                    "evidence_type": "delimiter_pair",
                    "confidence": "high",
                },
            ],
            [
                {
                    "artist": "JO YURI",
                    "title": "Farewell for now!",
                    "source": "music_section_only",
                    "section_index": 0,
                },
                {
                    "artist": "YENA",
                    "title": "It was love",
                    "source": "music_section_only",
                    "section_index": 1,
                },
            ],
        )

        self.assertEqual(len(updated), 2)
        self.assertEqual([c["merge_decision"] for c in candidates], ["excluded", "excluded"])
        self.assertEqual(candidates[0]["debug_reason"], "duplicate_music_section_artist_position")


if __name__ == "__main__":
    unittest.main()
