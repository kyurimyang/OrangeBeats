import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.spotify_api import search_artists_query, search_tracks_query
from app.services import spotify_http
from app.services.spotify_exceptions import SpotifyServiceError


class SpotifyHttpRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.rate_limit_file = Path(self.tmpdir.name) / "spotify_rate_limit.json"
        self.original_file = spotify_http._RATE_LIMIT_FILE
        self.original_until = spotify_http._rate_limited_until
        self.original_message = spotify_http._rate_limit_message
        spotify_http._RATE_LIMIT_FILE = self.rate_limit_file
        spotify_http._rate_limited_until = 0.0
        spotify_http._rate_limit_message = None

    def tearDown(self):
        spotify_http._RATE_LIMIT_FILE = self.original_file
        spotify_http._rate_limited_until = self.original_until
        spotify_http._rate_limit_message = self.original_message
        self.tmpdir.cleanup()

    @patch("app.services.spotify_http.requests.request")
    def test_429_response_is_persisted(self, request_mock):
        response = Mock()
        response.status_code = 429
        response.headers = {"Retry-After": "120"}
        request_mock.return_value = response

        with self.assertRaises(SpotifyServiceError) as ctx:
            spotify_http.spotify_request("GET", "https://api.spotify.com/v1/test", access_token="token")

        self.assertIn("retry_after=120", str(ctx.exception))
        self.assertTrue(self.rate_limit_file.exists())
        self.assertGreater(spotify_http._rate_limited_until, time.time())

    @patch("app.services.spotify_http.requests.request")
    def test_active_rate_limit_fails_fast_without_http_request(self, request_mock):
        spotify_http._save_rate_limit_state(60)

        with self.assertRaises(SpotifyServiceError):
            spotify_http.spotify_request("GET", "https://api.spotify.com/v1/test", access_token="token")

        request_mock.assert_not_called()

    @patch("app.services.spotify_api.spotify_request")
    def test_search_tracks_query_uses_track_type_kr_market_and_limit_five_max(self, request_mock):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"tracks": {"items": []}}
        request_mock.return_value = response

        search_tracks_query("token", "Ditto NewJeans", limit=10)

        request_mock.assert_called_once()
        _method, _url = request_mock.call_args.args[:2]
        params = request_mock.call_args.kwargs["params"]
        self.assertEqual(params["q"], "Ditto NewJeans")
        self.assertEqual(params["type"], "track")
        self.assertEqual(params["market"], "KR")
        self.assertEqual(params["limit"], 5)

    @patch("app.services.spotify_api.spotify_request")
    def test_search_artists_query_uses_artist_type_kr_market_and_limit_five_max(self, request_mock):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"artists": {"items": []}}
        request_mock.return_value = response

        search_artists_query("token", "IU", limit=10)

        request_mock.assert_called_once()
        params = request_mock.call_args.kwargs["params"]
        self.assertEqual(params["q"], "IU")
        self.assertEqual(params["type"], "artist")
        self.assertEqual(params["market"], "KR")
        self.assertEqual(params["limit"], 5)


if __name__ == "__main__":
    unittest.main()
