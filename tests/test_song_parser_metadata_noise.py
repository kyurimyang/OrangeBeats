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

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_thumbnail_credit_and_playlist_title_are_not_song_candidates(self, _direction_mock):
        result = parse_unstructured_lines_to_json(
            "\n".join(
                [
                    "\uc378\ub124\uc77c - Hearts2Hearts '\uc5d0\uc774\ub098&\uc720\ud558' \ub2d8",
                    "[ \ucd5c\uc2e0 \uac78\uadf8\ub8f9 \ub178\ub798 \ubaa8\uc74c - \ub290\uc88b \uc5ec\ub3cc \ub178\ub798 \ubaa8\uc74c / \uac78\uadf8\ub8f9 \ucf00\uc774\ud31d \ub178\ub3d9\uc694 / KPOP Playlist / \ucf00\uc774\ud31d \ud50c\ub808\uc774\ub9ac\uc2a4\ud2b8 / \ub9e4\uc7a5\uc5d0\uc11c \ud2c0\uae30 \uc88b\uc740 \ub178\ub798 ]",
                    "Hearts2Hearts - RUDE!",
                ]
            )
        )

        self.assertEqual(
            [(song["artist"], song["title"]) for song in result["songs"]],
            [("Hearts2Hearts", "RUDE!")],
        )


class ArtistTitleSplitProtectionTests(unittest.TestCase):
    """이미 정상적으로 파싱된 ARTIST - TITLE 구조가 후처리에서 망가지지 않는지 검증."""

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_two_word_english_title_is_not_re_split_as_compilation(self, _):
        # "TREASURE - KING KONG" → artist=KING, title=KONG 으로 오탐하면 안 됨
        result = parse_unstructured_lines_to_json("TREASURE - KING KONG")
        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["artist"], "TREASURE")
        self.assertEqual(songs[0]["title"], "KING KONG")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_korean_artist_english_two_word_title_not_split(self, _):
        # "빅뱅 - FANTASTIC BABY" → artist=FANTASTIC, title=BABY 오탐 방지
        result = parse_unstructured_lines_to_json("빅뱅 - FANTASTIC BABY")
        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["artist"], "빅뱅")
        self.assertEqual(songs[0]["title"], "FANTASTIC BABY")

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_parenthetical_suffix_not_treated_as_title_in_compilation_split(self, _):
        # "제니 - Like JENNIE (Extended Remix)" → 괄호 안에서 잘리지 않고 전체 title 유지
        result = parse_unstructured_lines_to_json("제니 - Like JENNIE (Extended Remix)")
        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["artist"], "제니")
        self.assertIn("Like JENNIE", songs[0]["title"])

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_three_word_title_with_apostrophe_not_split(self, _):
        # "ITZY - THAT'S NO NO" → artist=ITZY, title=THAT'S NO NO
        result = parse_unstructured_lines_to_json("ITZY - THAT'S NO NO")
        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["artist"], "ITZY")
        self.assertIn("NO NO", songs[0]["title"])

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_fx_artist_with_parenthetical_identifier(self, _):
        # "f(x) - Electric Shock" → artist=f(x), title=Electric Shock
        result = parse_unstructured_lines_to_json("f(x) - Electric Shock")
        songs = result["songs"]
        self.assertEqual(len(songs), 1)
        self.assertIn("f", songs[0]["artist"].lower())
        self.assertIn("Electric", songs[0]["title"])

    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "artist_title", "confidence": "high", "reason": ""},
    )
    def test_multiple_kpop_lines_preserve_artist_title(self, _):
        lines = [
            "TREASURE - KING KONG",
            "빅뱅 - FANTASTIC BABY",
            "ITZY - THAT'S NO NO",
        ]
        result = parse_unstructured_lines_to_json("\n".join(lines))
        pairs = [(s["artist"], s["title"]) for s in result["songs"]]
        self.assertIn(("TREASURE", "KING KONG"), pairs)
        self.assertIn(("빅뱅", "FANTASTIC BABY"), pairs)


if __name__ == "__main__":
    unittest.main()
