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

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "mixed", "confidence": "low", "reason": ""},
    )
    def test_timestamp_title_only_lines_drop_title_number_prefix(self, _llm_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "00:53 01. Supernatural",
                    "04:01 02. How Sweet",
                ]
            )
        )

        songs = result["songs"]
        self.assertEqual(
            [song["title"] for song in songs],
            ["Supernatural", "How Sweet"],
        )
        self.assertEqual(
            [song.get("timestamp") for song in songs],
            ["00:53", "04:01"],
        )

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_ampersand_title_is_not_resplit_as_next_artist(self, _llm_mock):
        result = parse_unstructured_lines_to_json("41:32 TWICE - YOUNG & WILD")

        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["artist"], "TWICE")
        self.assertEqual(songs[0]["title"], "YOUNG & WILD")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "title_artist", "confidence": "high", "reason": ""},
    )
    def test_timestamp_bullet_title_artist_keeps_multiword_artist_and_with_title(self, _llm_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "00:00 — Trigger the Fever - NCT DREAM",
                    "13:15 — Rock with you - 세븐틴 (SEVENTEEN)",
                ]
            )
        )

        songs = result["songs"]
        self.assertEqual(
            [(song["artist"], song["title"]) for song in songs],
            [
                ("NCT DREAM", "Trigger the Fever"),
                ("세븐틴", "Rock with you"),
            ],
        )
        self.assertEqual([song.get("timestamp") for song in songs], ["00:00", "13:15"])


if __name__ == "__main__":
    unittest.main()
