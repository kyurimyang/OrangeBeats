import unittest
from unittest.mock import patch

from app.parsers.song_parser import parse_unstructured_lines_to_json
from app.services.spotify_matching import _score_tracks, _track_dedupe_key


def track(name, artists):
    return {
        "id": f"{name}:{','.join(artists)}",
        "uri": f"spotify:track:{name}",
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {"name": "Test Album", "images": []},
        "popularity": 50,
    }


class TitleMetadataHintTests(unittest.TestCase):
    @patch(
        "app.parsers.song_parser._detect_llm_global_direction",
        return_value={"global_direction": "mixed", "confidence": "low", "reason": ""},
    )
    def test_feat_parenthetical_is_removed_from_title_and_kept_as_hint(self, _direction_mock):
        result = parse_unstructured_lines_to_json("코드쿤스트 - XI (Feat. 이하이)")

        song = result["songs"][0]
        self.assertEqual(song["artist"], "코드쿤스트")
        self.assertEqual(song["title"], "XI")
        self.assertEqual(song["title_feature_artists"], ["이하이"])
        self.assertIn("feat 이하이", song["title_metadata_hints"])

    def test_title_metadata_hint_is_used_as_featured_artist_evidence(self):
        candidate = track("XI", ["CODE KUNST", "LeeHi"])
        scored = _score_tracks(
            [candidate],
            {
                _track_dedupe_key(candidate): {
                    "query_type": "primary",
                    "query_used": 'track:"XI" artist:"CODE KUNST"',
                }
            },
            input_title="XI",
            input_artist="CODE KUNST",
            chosen_case="original",
            title_metadata_hints={
                "title_metadata_hints": ["feat LeeHi"],
                "title_feature_artists": ["LeeHi"],
                "title_producer_artists": [],
            },
        )

        detail = scored[0]["score_detail"]
        self.assertIn("featured_artist_metadata", detail["variant_pattern_tags"])
        self.assertEqual(detail["multi_artist_expected"], 2)
        self.assertEqual(detail["multi_artist_matched"], 2)


if __name__ == "__main__":
    unittest.main()
