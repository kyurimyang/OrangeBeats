import unittest

from app.services.analysis_flow import classify_text_analysis, merge_song_sources


class AnalysisFlowTests(unittest.TestCase):
    def test_classifies_text_partial_when_song_count_is_low(self):
        state = classify_text_analysis(
            {"success": True, "metrics": {"avg_completeness": 1.0}},
            [{"artist": "IU", "title": "Celebrity"}],
        )

        self.assertEqual(state["analysis_state"], "partial_success")
        self.assertTrue(state["needs_fallback"])
        self.assertEqual(state["next_action"], "choose_fallback")

    def test_classifies_text_success_when_enough_complete_songs(self):
        state = classify_text_analysis(
            {"success": True, "metrics": {"avg_completeness": 1.0}},
            [
                {"artist": "IU", "title": "Celebrity"},
                {"artist": "IU", "title": "Good Day"},
                {"artist": "IU", "title": "Palette"},
            ],
        )

        self.assertEqual(state["analysis_state"], "text_success")
        self.assertFalse(state["needs_fallback"])
        self.assertEqual(state["next_action"], "match_candidates")

    def test_merge_song_sources_dedupes_and_preserves_source_order(self):
        merged = merge_song_sources(
            [{"artist": "IU", "title": "Celebrity", "score": 0.5}],
            [
                {"artist": "IU", "title": "Celebrity", "score": 0.9},
                {"artist": "IU", "title": "Good Day"},
            ],
            fallback_source="ocr",
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["sources"], ["text", "ocr"])
        self.assertEqual(merged[0]["score"], 0.5)
        self.assertEqual(merged[1]["source"], "ocr")


if __name__ == "__main__":
    unittest.main()
