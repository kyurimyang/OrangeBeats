import unittest
from unittest.mock import patch

from app.parsers.song_parser import normalize_song_candidates
from app.services.spotify_matching import _build_case_queries


class SwapAndAliasMetadataTests(unittest.TestCase):
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "mixed", "confidence": "low", "reason": ""},
    )
    def test_swap_detected_adds_original_and_corrected_input_metadata(self, _direction_mock):
        result = normalize_song_candidates(
            {
                "songs": [
                    {
                        "artist": "Good Day",
                        "title": "IU",
                        "left": "Good Day",
                        "right": "IU",
                    }
                ]
            }
        )

        song = result["songs"][0]
        self.assertEqual(song["artist"], "IU")
        self.assertEqual(song["title"], "Good Day")
        self.assertEqual(song["normalized_by"], "swap_detected")
        self.assertEqual(song["original_input"], {"artist": "Good Day", "title": "IU"})
        self.assertEqual(song["corrected_input"], {"artist": "IU", "title": "Good Day"})

    def test_non_korean_alias_query_count_stays_capped(self):
        queries = _build_case_queries("Ditto", "NewJeans")

        self.assertEqual(
            [query["query"] for query in queries],
            ['track:"Ditto" artist:"NewJeans"', "Ditto NewJeans", "Ditto"],
        )
        self.assertLessEqual(len(queries), 3)


if __name__ == "__main__":
    unittest.main()
