import unittest

from app.services.spotify_common import compute_match_score
from app.services.spotify_matching import _classify_candidate, _score_tracks


def track(name, artists, popularity=50):
    return {
        "id": f"{name}:{','.join(artists)}",
        "uri": f"spotify:track:{name}",
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {"name": "Test Album"},
        "popularity": popularity,
    }


class SpotifyMatchingScoringTests(unittest.TestCase):
    def test_exact_match_is_high_confidence(self):
        score, detail = compute_match_score("The Last", "Yoon Sang", track("The Last", ["Yoon Sang"]))

        self.assertGreaterEqual(score, 0.85)
        self.assertGreaterEqual(detail["title_score"], 0.99)
        self.assertGreaterEqual(detail["artist_score"], 0.99)

    def test_title_exact_artist_spelling_gap_is_probable_or_better(self):
        scored = _score_tracks(
            [track("Short Hair", ["Girl's Day"])],
            {},
            input_title="Short Hair",
            input_artist="\uac78\uc2a4\ub370\uc774",
            chosen_case="original",
        )

        self.assertGreaterEqual(scored[0]["score"], 0.78)
        self.assertIn(_classify_candidate(scored[0], has_artist=True, input_artist="\uac78\uc2a4\ub370\uc774"), {"matched", "probable_match"})
        self.assertIn("title_exact_artist_spelling_gap_floor", scored[0]["score_detail"]["bonuses"])

    def test_artist_exact_title_spelling_gap_is_probable(self):
        scored = _score_tracks(
            [track("Short Hair", ["Girl's Day"])],
            {},
            input_title="\ub2e8\ubc1c\uba38\ub9ac",
            input_artist="Girl's Day",
            chosen_case="original",
        )

        self.assertGreaterEqual(scored[0]["score"], 0.72)
        self.assertEqual(_classify_candidate(scored[0], has_artist=True, input_artist="Girl's Day"), "probable_match")
        self.assertIn("artist_exact_title_spelling_gap_floor", scored[0]["score_detail"]["bonuses"])

    def test_parenthetical_version_is_penalized_but_not_discarded(self):
        score, detail = compute_match_score("The Last", "Yoon Sang", track("The Last - Remastered", ["Yoon Sang"]))

        self.assertGreater(score, 0.65)
        self.assertGreater(detail["version_penalty"], 0)

    def test_unrelated_song_stays_below_failed_threshold(self):
        score, _ = compute_match_score("The Last", "Yoon Sang", track("Shape of You", ["Ed Sheeran"]))

        self.assertLess(score, 0.50)

    def test_karaoke_candidate_is_capped_as_unmatched(self):
        scored = _score_tracks(
            [track("The Last Karaoke", ["KY Noraebang"])],
            {},
            input_title="The Last",
            input_artist="Yoon Sang",
            chosen_case="original",
        )

        self.assertLess(scored[0]["score"], 0.50)
        self.assertIn("non_original_audio_pattern", scored[0]["score_detail"]["pattern_tags"])

    def test_short_title_false_positive_is_penalized(self):
        scored = _score_tracks(
            [track("Love Is a Beautiful Pain", ["Someone Else"])],
            {},
            input_title="Love",
            input_artist="Yoon Sang",
            chosen_case="original",
        )

        self.assertLess(scored[0]["score"], 0.70)
        self.assertIn("short_title_false_positive_pattern", scored[0]["score_detail"]["pattern_tags"])


if __name__ == "__main__":
    unittest.main()
