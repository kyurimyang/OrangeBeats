import unittest

from app.clients.youtube_client import parse_youtube_target
from app.services.youtube_thumbnail import extract_video_id


class YouTubeUrlParsingTests(unittest.TestCase):
    def test_youtu_be_share_url_with_si_param_extracts_video_id(self):
        url = "https://youtu.be/HEaoCxnyjnk?si=goEvPr4c5FjEc-eW"

        self.assertEqual(parse_youtube_target(url), {"type": "video", "id": "HEaoCxnyjnk"})
        self.assertEqual(extract_video_id(url), "HEaoCxnyjnk")


if __name__ == "__main__":
    unittest.main()
