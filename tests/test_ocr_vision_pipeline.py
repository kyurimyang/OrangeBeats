import tempfile
import unittest
from unittest.mock import patch

from app.ocr import ocr_reader
from app.ocr.ocr_pipeline import run_ocr_pipeline


class OcrVisionPipelineTests(unittest.TestCase):
    def test_ocr_reader_imports_without_openai_api_key(self):
        with patch.object(ocr_reader, "OPENAI_API_KEY", None), patch.object(ocr_reader, "_client", None):
            self.assertEqual(ocr_reader.read_text_from_image("unused.jpg"), "")

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


if __name__ == "__main__":
    unittest.main()
