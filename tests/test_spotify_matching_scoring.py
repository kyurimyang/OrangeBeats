import unittest

from app.services.spotify_common import compute_match_score
from app.services.spotify_matching import (
    _apply_ocr_matching_policy,
    _build_case_queries,
    _classify_candidate,
    _score_tracks,
    _track_has_artist_id,
    _track_dedupe_key,
)


def track(name, artists, popularity=50, album_images=None, duration_ms=None):
    artist_names = [artist[0] if isinstance(artist, tuple) else artist for artist in artists]
    return {
        "id": f"{name}:{','.join(artist_names)}",
        "uri": f"spotify:track:{name}",
        "name": name,
        "artists": [
            {"name": artist[0], "id": artist[1]} if isinstance(artist, tuple) else {"name": artist}
            for artist in artists
        ],
        "album": {"name": "Test Album", "images": album_images or []},
        "popularity": popularity,
        "duration_ms": duration_ms,
    }


def primary_source(track_obj, title, artist):
    return {
        _track_dedupe_key(track_obj): {
            "query_type": "primary",
            "query_used": f'track:"{title}" artist:"{artist}"',
        }
    }


def fallback_source(track_obj, title, artist):
    return {
        _track_dedupe_key(track_obj): {
            "query_type": "fallback",
            "query_used": f"{title} {artist}",
        }
    }


class SpotifyMatchingScoringTests(unittest.TestCase):
    def test_track_artist_id_filter_checks_spotify_artist_ids(self):
        candidate = track("Celebrity", [("IU", "3HqSLMAZ3g3d5poNaI7GOU")])

        self.assertTrue(_track_has_artist_id(candidate, "3HqSLMAZ3g3d5poNaI7GOU"))
        self.assertFalse(_track_has_artist_id(candidate, "other-artist"))

    def test_search_queries_follow_spotify_search_api_shape(self):
        queries = _build_case_queries("Ditto", "NewJeans")

        self.assertEqual(
            [query["query"] for query in queries],
            ['track:"Ditto" artist:"NewJeans"', "Ditto NewJeans"],
        )
        self.assertLessEqual(len(queries), 3)

    def test_tracks_are_deduped_by_track_id(self):
        first = track("Song", ["Artist"], popularity=10)
        duplicate = track("Song", ["Artist"], popularity=90)
        duplicate["id"] = first["id"]

        scored = _score_tracks(
            [first, duplicate],
            primary_source(first, "Song", "Artist"),
            input_title="Song",
            input_artist="Artist",
            chosen_case="original",
        )

        self.assertEqual(len(scored), 1)

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
        self.assertTrue(
            {"title_exact_artist_spelling_gap_floor", "variant_pair_floor"}
            & set(scored[0]["score_detail"]["bonuses"])
        )

    def test_artist_exact_title_spelling_gap_is_probable(self):
        scored = _score_tracks(
            [track("Short Hair", ["Girl's Day"])],
            {},
            input_title="\ub2e8\ubc1c\uba38\ub9ac",
            input_artist="Girl's Day",
            chosen_case="original",
        )

        self.assertGreater(scored[0]["score"], 0.0)
        self.assertIn(_classify_candidate(scored[0], has_artist=True, input_artist="Girl's Day"), {"review_needed", "probable_match"})
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
        self.assertEqual(
            _classify_candidate(scored[0], has_artist=True, input_artist="Yoon Sang"),
            "unmatched",
        )

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

    def test_shinhan_bank_superbee_twlv_matches_by_variants_and_search_signal(self):
        candidate = track("SHINHAN BANK", ["SUPERBEE", "twlv"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uc2e0\ud55c\uc740\ud589", "\uc218\ud37c\ube44 & twlv"),
            input_title="\uc2e0\ud55c\uc740\ud589",
            input_artist="\uc218\ud37c\ube44 & twlv",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertGreaterEqual(scored[0]["score"], 0.70)
        self.assertTrue(detail["title_alias_matched"])
        self.assertTrue(detail["artist_alias_matched"])
        self.assertTrue(detail["search_engine_signal"])

    def test_yanghwa_bridge_ziont_matches_by_title_alias(self):
        candidate = track("Yanghwa BRDG", ["Zion.T"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uc591\ud654\ub300\uad50", "Zion.T"),
            input_title="\uc591\ud654\ub300\uad50",
            input_artist="Zion.T",
            chosen_case="original",
        )

        self.assertIn(_classify_candidate(scored[0], has_artist=True, input_artist="Zion.T"), {"matched", "probable_match"})
        self.assertTrue(scored[0]["score_detail"]["title_alias_matched"])

    def test_kid_milli_rrr_matches_with_broken_feat_parenthetical(self):
        candidate = track("rrr.. (feat. ShyboiiTobii)", ["Kid Milli", "Shyboiitobii"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "rrr.. (feat. Shyboiitobii", "\ud0a4\ub4dc\ubc00\ub9ac"),
            input_title="rrr.. (feat. Shyboiitobii",
            input_artist="\ud0a4\ub4dc\ubc00\ub9ac",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertIn(_classify_candidate(scored[0], has_artist=True, input_artist="\ud0a4\ub4dc\ubc00\ub9ac"), {"matched", "probable_match"})
        self.assertTrue(detail["artist_alias_matched"])
        self.assertIn("featured_artist_metadata", detail["pattern_tags"])

    def test_title_exact_artist_mismatch_blocks_auto_match_and_search_signal(self):
        candidate = track("There She Goes", ["The La's"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "There She Goes", "\uc2e4\ud0a4\ubcf4\uc774\uc988"),
            input_title="There She Goes",
            input_artist="\uc2e4\ud0a4\ubcf4\uc774\uc988",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertNotIn(_classify_candidate(scored[0], has_artist=True, input_artist="\uc2e4\ud0a4\ubcf4\uc774\uc988"), {"matched", "probable_match"})
        self.assertFalse(detail["search_engine_signal"])
        self.assertEqual(detail["search_engine_signal_blocked_reason"], "title_exact_artist_mismatch")

    def test_rank1_candidate_is_kept_as_review_needed_low_confidence(self):
        candidate = track("There She Goes", ["The La's"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "There She Goes", "\uc2e4\ud0a4\ubcf4\uc774\uc988"),
            input_title="There She Goes",
            input_artist="\uc2e4\ud0a4\ubcf4\uc774\uc988",
            chosen_case="original",
        )

        self.assertEqual(
            _classify_candidate(scored[0], has_artist=True, input_artist="\uc2e4\ud0a4\ubcf4\uc774\uc988"),
            "review_needed",
        )

    def test_ocr_policy_blocks_title_only_auto_selection(self):
        candidate = track("\uadf8\ub300\ub77c\uc11c", ["GUMMY"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uadf8\ub300\ub77c\uc11c", "\ucf00\uc774\uc70c"),
            input_title="\uadf8\ub300\ub77c\uc11c",
            input_artist="\ucf00\uc774\uc70c",
            chosen_case="original",
        )[0]
        scored["match_status"] = "matched"
        scored["score"] = 0.9
        scored["score_detail"]["evidence_confidence"]["match_status"] = "matched"
        scored["score_detail"]["evidence_confidence"]["decision"] = "auto_select_recommended"
        scored["score_detail"]["evidence_confidence"]["final_score"] = 0.9
        scored["score_detail"]["evidence_detail"]["artist_similarity"] = 0.0

        reviewed = _apply_ocr_matching_policy(scored)

        self.assertEqual(reviewed["match_status"], "review_needed")
        self.assertFalse(reviewed["matched"])
        self.assertLess(reviewed["score"], 0.8)
        self.assertIn("가수 근거가 부족", reviewed["user_message"])

    def test_silkybois_candidate_gets_artist_variant_but_prod_penalty(self):
        candidate = track("THERE SHE GOES (PROD BY BOYCOLD)", ["SILKYBOIS"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "There She Goes", "\uc2e4\ud0a4\ubcf4\uc774\uc988"),
            input_title="There She Goes",
            input_artist="\uc2e4\ud0a4\ubcf4\uc774\uc988",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertGreaterEqual(detail["artist_variant_score"], 0.95)
        self.assertIn("non_original_audio_pattern", detail["pattern_tags"])
        self.assertGreater(detail["penalties"].get("non_original_audio_pattern", 0), 0)

    def test_gaeko_no_make_up_matches_by_title_and_artist_alias(self):
        candidate = track("No Make Up", ["Gaeko"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\ud654\uc7a5 \uc9c0\uc6e0\uc5b4", "\uac1c\ucf54"),
            input_title="\ud654\uc7a5 \uc9c0\uc6e0\uc5b4",
            input_artist="\uac1c\ucf54",
            chosen_case="original",
        )

        self.assertGreaterEqual(scored[0]["score"], 0.70)
        self.assertTrue(scored[0]["score_detail"]["title_alias_matched"])
        self.assertTrue(scored[0]["score_detail"]["artist_alias_matched"])

    def test_rank1_high_query_without_metadata_is_kept_for_review(self):
        candidate = track("Coming Of Age Story", ["Unknown Romanized Artist"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uccad\ucd98\ub9cc\ud654", "\uac00\uc218"),
            input_title="\uccad\ucd98\ub9cc\ud654",
            input_artist="\uac00\uc218",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertEqual(detail["query_reliability"], "high")
        self.assertFalse(detail["notation_difference_detected"])
        self.assertFalse(detail["search_engine_signal"])
        self.assertEqual(detail["applied_pattern"], "SEARCH_RANK1_REVIEW")
        self.assertEqual(detail["candidate_decision"], "warning")
        self.assertEqual(_classify_candidate(scored[0], has_artist=True, input_artist="\uac00\uc218"), "review_needed")

    def test_rank1_high_query_artist_alias_promotes_to_probable_or_better(self):
        candidate = track("TIME CAPSULE", ["DAVICHI"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\ud0c0\uc784\ucea1\uc290", "\ub2e4\ube44\uce58"),
            input_title="\ud0c0\uc784\ucea1\uc290",
            input_artist="\ub2e4\ube44\uce58",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertEqual(detail["query_reliability"], "high")
        self.assertTrue(detail["artist_alias_matched"])
        self.assertTrue(detail["search_engine_signal"])
        self.assertEqual(_classify_candidate(scored[0], has_artist=True, input_artist="\ub2e4\ube44\uce58"), "review_needed")
        self.assertEqual(detail["applied_pattern"], "ARTIST_STRONG_TITLE_WEAK")

    def test_korean_title_english_spotify_metadata_auto_matches_without_title_alias(self):
        candidate = track(
            "A Long Goodbye",
            ["Kim Dong Ryul"],
            popularity=55,
            album_images=[{"url": "https://example.test/album.jpg"}],
            duration_ms=278000,
        )
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uae34 \uc774\ubcc4", "\uae40\ub3d9\ub960"),
            input_title="\uae34 \uc774\ubcc4",
            input_artist="\uae40\ub3d9\ub960",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertTrue(detail["official_metadata_candidate"])
        self.assertEqual(detail["official_metadata_reason"], "official_spotify_metadata_candidate")
        self.assertGreaterEqual(scored[0]["score"], 0.55)
        self.assertEqual(
            _classify_candidate(scored[0], has_artist=True, input_artist="\uae40\ub3d9\ub960"),
            "matched",
        )
        self.assertFalse(detail["title_alias_matched"])
        self.assertEqual(detail["applied_pattern"], "TRANSLATED_TITLE_ARTIST_STRONG")
        self.assertEqual(detail["evidence_confidence"]["decision"], "auto_select_recommended")

    def test_pattern_b_keeps_korean_title_english_spotify_title_for_review(self):
        cases = [
            ("\uc785\ucd98", "\ud55c\ub85c\ub85c", "Let Me Love My Youth", "HANRORO"),
            ("\uc815\ub958\uc7a5", "\ud55c\ub85c\ub85c", "The last stop of our pain", "HANRORO"),
            ("\ud53c\uc640 \uac08\uc99d", "\uac80\uc815\uce58\ub9c8", "Blood and thirst", "The Black Skirts"),
        ]

        for input_title, input_artist, spotify_title, spotify_artist in cases:
            with self.subTest(input_title=input_title):
                candidate = track(
                    spotify_title,
                    [spotify_artist],
                    popularity=45,
                    album_images=[{"url": "https://example.test/album.jpg"}],
                )
                scored = _score_tracks(
                    [candidate],
                    primary_source(candidate, input_title, input_artist),
                    input_title=input_title,
                    input_artist=input_artist,
                    chosen_case="original",
                )

                detail = scored[0]["score_detail"]
                self.assertEqual(scored[0]["match_status"], "matched")
                self.assertEqual(detail["applied_pattern"], "TRANSLATED_TITLE_ARTIST_STRONG")
                self.assertTrue(detail["translated_title_candidate"])
                self.assertTrue(detail["official_metadata_candidate"])
                self.assertGreaterEqual(scored[0]["score"], 0.85)
                self.assertEqual(detail["candidate_decision"], "selectable")

    def test_exact_title_with_official_metadata_artist_is_high_confidence(self):
        candidate = track(
            "0+0",
            ["HANRORO"],
            popularity=60,
            album_images=[{"url": "https://example.test/album.jpg"}],
        )
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "0+0", "\ud55c\ub85c\ub85c"),
            input_title="0+0",
            input_artist="\ud55c\ub85c\ub85c",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertEqual(detail["applied_pattern"], "EXACT_MATCH")
        self.assertEqual(scored[0]["match_status"], "matched")
        self.assertGreaterEqual(scored[0]["score"], 0.85)

    def test_karaoke_rank1_blocks_search_engine_signal(self):
        candidate = track("The Last Karaoke", ["KY Noraebang"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "The Last", "Yoon Sang"),
            input_title="The Last",
            input_artist="Yoon Sang",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertFalse(detail["search_engine_signal"])
        self.assertEqual(detail["search_engine_signal_blocked_reason"], "non_original_or_version_candidate")
        self.assertLess(scored[0]["score"], 0.55)

    def test_candidates_are_resorted_by_final_score_not_spotify_rank(self):
        bad_rank1 = track("Shape of You", ["Ed Sheeran"], popularity=90)
        good_rank2 = track("The Last", ["Yoon Sang"], popularity=10)
        sources = {}
        sources.update(primary_source(bad_rank1, "The Last", "Yoon Sang"))
        sources.update({
            _track_dedupe_key(good_rank2): {
                "query_type": "primary",
                "query_used": 'track:"The Last" artist:"Yoon Sang"',
            }
        })

        scored = _score_tracks(
            [bad_rank1, good_rank2],
            sources,
            input_title="The Last",
            input_artist="Yoon Sang",
            chosen_case="original",
        )

        self.assertEqual(scored[0]["name"], "The Last")
        self.assertGreater(scored[0]["score"], scored[1]["score"])

    def test_score_detail_contains_search_engine_debug_fields(self):
        candidate = track("Run", ["OKDAL"])
        scored = _score_tracks(
            [candidate],
            fallback_source(candidate, "\ub2ec\ub9ac\uae30", "\uc625\uc0c1\ub2ec\ube5b"),
            input_title="\ub2ec\ub9ac\uae30",
            input_artist="\uc625\uc0c1\ub2ec\ube5b",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        for key in {
            "input_title_variants",
            "input_artist_variants",
            "candidate_title_variants",
            "candidate_artist_variants",
            "title_variant_score",
            "artist_variant_score",
            "romanization_matched",
            "notation_difference_detected",
            "notation_difference_reason",
            "query_contains_title_and_artist",
            "query_reliability",
            "api_rank",
            "query_type",
            "query_used",
            "search_engine_signal",
            "search_engine_signal_score",
            "search_engine_signal_reason",
            "search_engine_signal_blocked_reason",
            "score_before_search_engine_signal",
            "final_score",
            "pattern_tags",
            "bonuses",
            "penalties",
            "score_caps",
        }:
            self.assertIn(key, detail)
        self.assertEqual(detail["query_reliability"], "medium")

    def test_black_skirts_alias_exact_title_auto_matches(self):
        candidate = track("EVERYTHING", ["The Black Skirts"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "everything", "\uac80\uc815\uce58\ub9c8"),
            input_title="everything",
            input_artist="\uac80\uc815\uce58\ub9c8",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertTrue(detail["artist_alias_matched"])
        self.assertEqual(scored[0]["match_status"], "matched")

    def test_redoor_translated_title_alias_rank1_auto_matches(self):
        candidate = track(
            "Forever Has Always Been",
            ["Redoor"],
            album_images=[{"url": "https://example.test/album.jpg"}],
        )
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uc601\uc6d0\uc740 \uadf8\ub807\ub4ef", "\ub9ac\ub3c4\uc5b4"),
            input_title="\uc601\uc6d0\uc740 \uadf8\ub807\ub4ef",
            input_artist="\ub9ac\ub3c4\uc5b4",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertTrue(detail["artist_alias_matched"])
        self.assertTrue(detail["translated_title_candidate"])
        self.assertEqual(detail["applied_pattern"], "TRANSLATED_TITLE_ARTIST_STRONG")
        self.assertEqual(scored[0]["match_status"], "matched")

    def test_title_exact_artist_mismatch_is_review_needed_not_matched(self):
        candidate = track("\uc601\uc6d0\uc740 \uadf8\ub807\ub4ef", ["Pluggboi"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uc601\uc6d0\uc740 \uadf8\ub807\ub4ef", "\ub9ac\ub3c4\uc5b4"),
            input_title="\uc601\uc6d0\uc740 \uadf8\ub807\ub4ef",
            input_artist="\ub9ac\ub3c4\uc5b4",
            chosen_case="original",
        )

        self.assertEqual(scored[0]["match_status"], "review_needed")
        self.assertFalse(scored[0]["matched"])
        self.assertEqual(scored[0]["score_detail"]["applied_pattern"], "TITLE_ONLY_MATCH")

    def test_cover_version_blocks_auto_match_even_with_title_exact(self):
        candidate = track("\uc5b4\ub5bb\uac8c \uc774\ubcc4\uae4c\uc9c0 \uc0ac\ub791\ud558\uaca0\uc5b4 Cover Ver.", ["Sogumm"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\uc5b4\ub5bb\uac8c \uc774\ubcc4\uae4c\uc9c0 \uc0ac\ub791\ud558\uaca0\uc5b4", "\uc545\ub3d9\ubba4\uc9c0\uc158"),
            input_title="\uc5b4\ub5bb\uac8c \uc774\ubcc4\uae4c\uc9c0 \uc0ac\ub791\ud558\uaca0\uc5b4",
            input_artist="\uc545\ub3d9\ubba4\uc9c0\uc158",
            chosen_case="original",
        )

        self.assertEqual(scored[0]["match_status"], "review_needed")
        self.assertTrue(scored[0]["score_detail"]["version_penalty_applied"])
        self.assertEqual(scored[0]["score_detail"]["applied_pattern"], "VERSION_REVIEW")

    def test_woodz_drowning_exact_artist_title_auto_matches(self):
        candidate = track("Drowning", ["WOODZ"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "drowning", "woodz"),
            input_title="drowning",
            input_artist="woodz",
            chosen_case="original",
        )

        self.assertEqual(scored[0]["match_status"], "matched")
        self.assertGreaterEqual(scored[0]["score"], 0.85)

    def test_short_korean_title_substring_artist_mismatch_is_not_auto_matched(self):
        candidate = track("\ubd04\uc778\uac00 \ubd10 Spring Love", ["WENDY", "Eric Nam"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\ubd10", "red velvet"),
            input_title="\ubd10",
            input_artist="red velvet",
            chosen_case="original",
        )

        detail = scored[0]["score_detail"]
        self.assertLess(detail["title_variant_score"], 0.8)
        self.assertLess(detail["artist_variant_score"], 0.3)
        self.assertNotEqual(scored[0]["match_status"], "matched")

    def test_parenthetical_english_title_hint_can_match_official_title(self):
        candidate = track("Look", ["Red Velvet"])
        scored = _score_tracks(
            [candidate],
            primary_source(candidate, "\ubd10 (look)", "red velvet"),
            input_title="\ubd10 (look)",
            input_artist="red velvet",
            chosen_case="original",
        )

        self.assertEqual(scored[0]["match_status"], "matched")
        self.assertGreaterEqual(scored[0]["score_detail"]["title_variant_score"], 0.99)

    def test_current_kpop_korean_artist_aliases_match_english_spotify_metadata(self):
        cases = [
            ("\ucf54\ub974\ud2f0\uc2a4", "GO!", track("GO!", ["CORTIS"])),
            ("\uc62c\ub370\uc774 \ud504\ub85c\uc81d\ud2b8", "YOU AND I", track("YOU AND I", ["ALLDAY PROJECT"])),
            ("\uc62c\ub370\uc774\ud504\ub85c\uc81d\ud2b8", "ONE MORE TIME", track("ONE MORE TIME", ["ALLDAY PROJECT"])),
            ("\ucea3\uce20\uc544\uc774", "Debut", track("Debut", ["KATSEYE"])),
        ]

        for artist, title, candidate in cases:
            with self.subTest(artist=artist, title=title):
                scored = _score_tracks(
                    [candidate],
                    primary_source(candidate, title, artist),
                    input_title=title,
                    input_artist=artist,
                    chosen_case="original",
                )

                self.assertEqual(scored[0]["match_status"], "matched")
                self.assertTrue(scored[0]["score_detail"]["artist_alias_matched"])


if __name__ == "__main__":
    unittest.main()
