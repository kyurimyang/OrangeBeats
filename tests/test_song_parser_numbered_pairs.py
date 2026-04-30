import unittest
from unittest.mock import patch

from app.parsers.song_parser import parse_unstructured_lines_to_json


class SongParserNumberedPairsTests(unittest.TestCase):
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "mixed", "confidence": "low", "reason": ""},
    )
    def test_number_dash_title_dash_artist_lines_drop_track_number(self, _llm_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "1. - 처음 그 자리에 - 이보람",
                    "2. - I THINK I - 별",
                    "5. - ma boy - 시스타 19",
                    "6. - bubble love - 서인영, mc 몽",
                ]
            )
        )

        songs = result["songs"]
        self.assertEqual(
            [(song["title"], song["artist"]) for song in songs],
            [
                ("처음 그 자리에", "이보람"),
                ("I THINK I", "별"),
                ("ma boy", "시스타 19"),
                ("bubble love", "서인영, mc 몽"),
            ],
        )
        self.assertTrue(all(song.get("nested_pair_extracted") for song in songs))
        self.assertEqual([song.get("track_number_prefix") for song in songs], ["1.", "2.", "5.", "6."])


if __name__ == "__main__":
    unittest.main()
