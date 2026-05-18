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

    @patch("app.services.spotify_playlist.pick_best_track_match")
    @patch(
        "app.services.spotify_playlist.resolve_spotify_artist_id",
        return_value={"id": "cortis-id", "name": "CORTIS", "score": 1.0},
    )
    def test_music_section_confirmed_songs_do_not_use_single_artist_filter(self, resolve_mock, match_mock):
        match_mock.return_value = {
            "uri": "spotify:track:1",
            "name": "Treat You Better",
            "artists": ["Shawn Mendes"],
            "score": 0.95,
            "match_status": "matched",
            "top_candidates": [],
        }

        results = analyze_spotify_candidates(
            access_token="token",
            songs=[
                {"artist": "CORTIS", "title": "GO!", "artist_inferred": True},
                {
                    "artist": "Shawn Mendes",
                    "title": "Treat You Better",
                    "artist_inferred": False,
                    "music_section_confirmed": True,
                    "confidence": "high",
                },
            ],
        )

        confirmed_call = match_mock.call_args_list[1].kwargs
        self.assertEqual(confirmed_call["artist"], "Shawn Mendes")
        self.assertNotIn("spotify_artist_id", confirmed_call["song_meta"])
        self.assertFalse(results[1]["single_artist_filter_applied"])
        self.assertEqual(results[1]["single_artist_filter_reason"], "music_section_confirmed")

    @patch("app.services.spotify_playlist.pick_best_track_match")
    @patch(
        "app.services.spotify_playlist.resolve_spotify_artist_id",
        return_value={"id": "cortis-id", "name": "CORTIS", "score": 1.0},
    )
    def test_single_artist_filter_is_limited_to_inferred_unconfirmed_songs(self, resolve_mock, match_mock):
        match_mock.return_value = {
            "uri": "spotify:track:1",
            "name": "GO!",
            "artists": ["CORTIS"],
            "score": 0.95,
            "match_status": "matched",
            "top_candidates": [],
        }

        results = analyze_spotify_candidates(
            access_token="token",
            songs=[
                {"artist": "CORTIS", "title": "GO!", "artist_inferred": True, "music_section_confirmed": False},
                {"artist": "Harry Styles", "title": "As It Was", "artist_inferred": False, "confidence": "high"},
            ],
        )

        inferred_call = match_mock.call_args_list[0].kwargs
        high_conf_call = match_mock.call_args_list[1].kwargs
        self.assertIsNone(inferred_call["artist"])
        self.assertEqual(inferred_call["song_meta"]["spotify_artist_id"], "cortis-id")
        self.assertEqual(high_conf_call["artist"], "Harry Styles")
        self.assertNotIn("spotify_artist_id", high_conf_call["song_meta"])
        self.assertTrue(results[0]["single_artist_filter_applied"])
        self.assertFalse(results[1]["single_artist_filter_applied"])
        self.assertEqual(results[1]["single_artist_filter_reason"], "artist_not_inferred")


class TrackIdFromResultRowTests(unittest.TestCase):
    def test_track_id_from_spotify_uri(self):
        from app.services.spotify_playlist import _track_id_from_result_row

        self.assertEqual(
            _track_id_from_result_row({"spotify_uri": "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"}),
            "4iV5W9uYEdYUVa79Axb7Rh",
        )

    def test_track_id_from_open_web_url(self):
        from app.services.spotify_playlist import _track_id_from_result_row

        self.assertEqual(
            _track_id_from_result_row(
                {"spotify_uri": "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh?si=abc"}
            ),
            "4iV5W9uYEdYUVa79Axb7Rh",
        )

    def test_track_id_from_intl_web_url(self):
        from app.services.spotify_playlist import _track_id_from_result_row

        self.assertEqual(
            _track_id_from_result_row(
                {"spotify_uri": "https://open.spotify.com/intl-ko/track/4iV5W9uYEdYUVa79Axb7Rh"}
            ),
            "4iV5W9uYEdYUVa79Axb7Rh",
        )


if __name__ == "__main__":
    unittest.main()
