import unittest
from unittest.mock import patch

from app.parsers.song_parser import parse_unstructured_lines_to_json


class SongParserMetadataNoiseTests(unittest.TestCase):
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_provider_ost_and_explanatory_lines_are_not_song_candidates(self, _direction_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "Mitski - my love mine all mine",
                    "d4vd - here with me",
                    "Provided by Dead Oceans / Secretly Group",
                    "Provided by Darkroom / Interscope Records",
                    'OST: tvN \ub4dc\ub77c\ub9c8 "\ub610! \uc624\ud574\uc601" Part 7',
                    "\ud45c\ub958 - \ub354 \ud3f4\uc2a4\uc5d0 \uc801\ud600 \uc788\ub294 \ubb38\uc7a5\ub4e4\uc740 \ub2e4 \uc704\uc758 \uc2dc\uc9d1\uc5d0 \uc218\ub85d\ub418\uc5b4 \uc788\uad6c\uc694",
                    "Rules - The Volunteers\ub294 '\ubbf8\ub798\uc758 \uc190 - \ucc28\ub3c4\ud558'",
                    "\uccad\uc0c9\ub3d9\uacbd - \ud314\uce60\ub304\uc2a4\ub294 '\ucc9c\uc0ac\ub97c \uac70\ubd80\ud558\ub294 \uc6b0\uc6b8\ud55c \uc5f0\uc778\uc5d0\uac8c - \uc591\uc548\ub2e4' \uc2dc\uc9d1\uc5d0 \uc218\ub85d\ub41c \uc2dc \uc911 \ud558\ub098\uc758 \uc81c\ubaa9\uc785\ub2c8\ub2e4",
                ]
            )
        )

        self.assertEqual(
            [(song["artist"], song["title"]) for song in result["songs"]],
            [
                ("Mitski", "my love mine all mine"),
                ("d4vd", "here with me"),
            ],
        )

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_with_pronoun_is_preserved_in_title(self, _direction_mock):
        result = parse_unstructured_lines_to_json("d4vd - here with me")

        self.assertEqual(result["songs"][0]["artist"], "d4vd")
        self.assertEqual(result["songs"][0]["title"], "here with me")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_social_handle_pairs_are_not_song_candidates(self, _direction_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "ig : offwebkr",
                    "spotify : offweb",
                    "instagram : @offwebkr",
                    "Mitski - my love mine all mine",
                ]
            )
        )

        self.assertEqual(
            [(song["artist"], song["title"]) for song in result["songs"]],
            [("Mitski", "my love mine all mine")],
        )


if __name__ == "__main__":
    unittest.main()
