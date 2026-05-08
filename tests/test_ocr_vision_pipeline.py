import tempfile
import unittest
from unittest.mock import patch

from app.ocr import ocr_reader
from app.ocr.ocr_pipeline import build_vision_text, run_ocr_pipeline, select_representative_ocr_block
from app.services.fallback_extraction import extract_songs_with_ocr


class OcrVisionPipelineTests(unittest.TestCase):
    def test_ocr_reader_imports_without_openai_api_key(self):
        with patch.object(ocr_reader, "OPENAI_API_KEY", None), patch.object(ocr_reader, "_client", None):
            self.assertEqual(ocr_reader.read_text_from_image("unused.jpg"), "")

    def test_build_vision_text_dedupes_lines_and_drops_empty_timestamp_lines(self):
        result = build_vision_text(
            [
                {"text": "00:12\n00:15 Artist - Title\n\nSecond Artist - Second Title"},
                {"text": "artist - title\n01:03\nThird Artist - Third Title"},
            ]
        )

        self.assertEqual(
            result,
            "\n".join(
                [
                    "00:15 Artist - Title",
                    "Second Artist - Second Title",
                    "Third Artist - Third Title",
                ]
            ),
        )

    @patch("app.ocr.ocr_pipeline.read_text_from_image")
    @patch("app.ocr.ocr_pipeline.extract_frames")
    def test_pipeline_returns_structured_result_and_dedupes_text(self, extract_frames_mock, read_text_mock):
        extract_frames_mock.return_value = ["frame1.jpg", "frame2.jpg", "frame3.jpg"]
        read_text_mock.side_effect = ["Artist - Title", "Artist - Title", ""]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_ocr_pipeline(
                video_path="video.mp4",
                work_dir=tmpdir,
                interval_sec=30,
                max_frames=3,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(result["raw_text_count"], 1)
        self.assertEqual(result["combined_text"], "Artist - Title")
        extract_frames_mock.assert_called_once()

    def test_representative_block_prefers_contiguous_playlist_over_union_noise(self):
        selection = select_representative_ocr_block(
            [
                {
                    "frame_index": 0,
                    "text": "\n".join(
                        [
                            "Subscribe",
                            "일기예보 - 이젠안녕",
                            "instagram @noise",
                        ]
                    ),
                },
                {
                    "frame_index": 1,
                    "text": "\n".join(
                        [
                            "0:00 김형중 - 그녀가 웃잖아",
                            "4:25 토이 - 좋은 사람",
                            "8:31 더 넛츠 - 사랑의 바보",
                            "13:08 일기예보 - 인형의 꿈",
                            "17:03 뱅크 - 가질 수 없는 너",
                            "21:22 김광석 - 사랑했지만",
                        ]
                    ),
                },
                {"frame_index": 2, "text": "케이윌 - 그대라서\nGUMMY - 그대라서"},
            ]
        )

        self.assertEqual(selection["selected_block"]["frame_index"], 1)
        self.assertIn("김형중 - 그녀가 웃잖아", selection["selected_text"])
        self.assertNotIn("이젠안녕", selection["selected_text"])
        self.assertNotIn("GUMMY", selection["selected_text"])

    @patch("app.services.fallback_extraction.download_youtube_video", return_value="video.mp4")
    @patch("app.services.fallback_extraction._get_youtube_info", return_value={"duration": 120, "title": "Video"})
    @patch("app.services.fallback_extraction.run_ocr_pipeline")
    @patch("app.services.fallback_extraction.analyze_text_block")
    def test_explicit_ocr_mode_succeeds_when_any_song_is_extracted(
        self,
        analyze_text_mock,
        run_ocr_mock,
        _info_mock,
        _download_mock,
    ):
        run_ocr_mock.return_value = {
            "frame_count": 3,
            "raw_text_count": 1,
            "combined_text": "Artist - Title",
            "errors": [],
        }
        analyze_text_mock.return_value = {
            "stage": "vision",
            "success": False,
            "method": "rule_based",
            "signals": {},
            "metrics": {},
            "songs": [{"artist": "Artist", "title": "Title", "is_complete": True}],
        }

        result = extract_songs_with_ocr("https://www.youtube.com/watch?v=test")

        self.assertTrue(result["success"])
        self.assertEqual(result["songs"], [{"artist": "Artist", "title": "Title", "is_complete": True}])


if __name__ == "__main__":
    unittest.main()
