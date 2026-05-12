import unittest
from unittest.mock import patch

from app.services.spotify_playlist import analyze_spotify_candidates, create_playlist_from_songs


class SpotifyPlaylistOrderTests(unittest.TestCase):
    @patch("app.services.spotify_playlist.add_tracks_to_playlist")
    @patch("app.services.spotify_playlist.create_playlist")
    @patch("app.services.spotify_playlist.pick_best_track_match")
    def test_playlist_is_created_after_matching(self, match_mock, create_mock, add_mock):
        events = []

        def match_side_effect(**kwargs):
            events.append("match")
            return {
                "uri": "spotify:track:1",
                "name": "The Last",
                "artists": ["Yoon Sang"],
                "score": 0.95,
                "match_status": "matched",
                "top_candidates": [],
            }

        def create_side_effect(**kwargs):
            events.append("create")
            return {"id": "playlist-1", "external_urls": {"spotify": "https://open.spotify.com/playlist/1"}}

        def add_side_effect(**kwargs):
            events.append("add")
            return {}

        match_mock.side_effect = match_side_effect
        create_mock.side_effect = create_side_effect
        add_mock.side_effect = add_side_effect

        result = create_playlist_from_songs(
            access_token="token",
            playlist_name="Test",
            songs=[{"artist": "Yoon Sang", "title": "The Last"}],
        )

        self.assertEqual(events, ["match", "create", "add"])
        self.assertTrue(result["playlist_created"])
        self.assertEqual(result["playlist_id"], "playlist-1")

    @patch("app.services.spotify_playlist.add_tracks_to_playlist")
    @patch("app.services.spotify_playlist.create_playlist")
    @patch("app.services.spotify_playlist.pick_best_track_match", return_value=None)
    def test_playlist_is_not_created_when_no_tracks_are_matchable(self, match_mock, create_mock, add_mock):
        result = create_playlist_from_songs(
            access_token="token",
            playlist_name="Test",
            songs=[{"artist": "Unknown", "title": "Missing Song"}],
        )

        create_mock.assert_not_called()
        add_mock.assert_not_called()
        self.assertFalse(result["playlist_created"])
        self.assertIsNone(result["playlist_id"])
        self.assertEqual(result["unmatched_count"], 1)

    @patch("app.services.spotify_playlist.pick_best_track_match")
    @patch(
        "app.services.spotify_playlist.resolve_spotify_artist_id",
        return_value={"id": "3HqSLMAZ3g3d5poNaI7GOU", "name": "IU", "score": 1.0},
    )
    def test_single_artist_context_passes_spotify_artist_id_to_matching(self, resolve_mock, match_mock):
        match_mock.return_value = {
            "uri": "spotify:track:1",
            "name": "Celebrity",
            "artists": ["IU"],
            "score": 0.95,
            "match_status": "matched",
            "top_candidates": [],
        }

        results = analyze_spotify_candidates(
            access_token="token",
            songs=[
                {"artist": "IU", "title": "Celebrity", "artist_inferred": True},
                {"artist": "IU", "title": "Good Day", "artist_inferred": True},
            ],
        )

        resolve_mock.assert_called_once_with("token", "IU", market="KR")
        first_meta = match_mock.call_args_list[0].kwargs["song_meta"]
        self.assertEqual(first_meta["spotify_artist_id"], "3HqSLMAZ3g3d5poNaI7GOU")
        self.assertTrue(results[0]["single_artist_mode"])
        self.assertEqual(results[0]["spotify_artist_id_filter"], "3HqSLMAZ3g3d5poNaI7GOU")


if __name__ == "__main__":
    unittest.main()
