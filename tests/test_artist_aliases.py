import tempfile
import unittest
from pathlib import Path

from app.services import artist_aliases
from app.services.spotify_common import ARTIST_ALIAS_MAP, resolve_artist_alias


class ArtistAliasesTests(unittest.TestCase):
    def test_save_artist_alias_updates_file_and_runtime_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = artist_aliases.DATA_DIR
            original_file = artist_aliases.ALIASES_FILE
            original_aliases = dict(ARTIST_ALIAS_MAP)
            try:
                artist_aliases.DATA_DIR = Path(tmpdir)
                artist_aliases.ALIASES_FILE = Path(tmpdir) / "artist_aliases.json"

                saved = artist_aliases.save_artist_aliases([
                    {
                        "input_artist": "파우",
                        "spotify_artist": "POW",
                        "spotify_uri": "spotify:track:track-1",
                        "spotify_title": "Valentine",
                        "album_image": "https://example.test/cover.jpg",
                    }
                ])

                self.assertEqual(saved, 1)
                self.assertEqual(resolve_artist_alias("파우"), "POW")

                stored_text = artist_aliases.ALIASES_FILE.read_text(encoding="utf-8")
                self.assertIn('"input_artist": "파우"', stored_text)
                self.assertIn('"spotify_artist": "POW"', stored_text)
                self.assertNotIn("spotify:track:track-1", stored_text)
                self.assertNotIn("album_image", stored_text)
            finally:
                artist_aliases.DATA_DIR = original_dir
                artist_aliases.ALIASES_FILE = original_file
                ARTIST_ALIAS_MAP.clear()
                ARTIST_ALIAS_MAP.update(original_aliases)

    def test_clear_artist_aliases_returns_deleted_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = artist_aliases.DATA_DIR
            original_file = artist_aliases.ALIASES_FILE
            original_aliases = dict(ARTIST_ALIAS_MAP)
            try:
                artist_aliases.DATA_DIR = Path(tmpdir)
                artist_aliases.ALIASES_FILE = Path(tmpdir) / "artist_aliases.json"

                artist_aliases.save_artist_aliases([
                    {
                        "input_artist": "Artist",
                        "spotify_artist": "Spotify Artist",
                    }
                ])

                deleted_count = artist_aliases.clear_artist_aliases()

                self.assertEqual(deleted_count, 1)
                self.assertEqual(artist_aliases.ALIASES_FILE.read_text(encoding="utf-8"), "[]")
                self.assertNotEqual(resolve_artist_alias("Artist"), "Spotify Artist")
            finally:
                artist_aliases.DATA_DIR = original_dir
                artist_aliases.ALIASES_FILE = original_file
                ARTIST_ALIAS_MAP.clear()
                ARTIST_ALIAS_MAP.update(original_aliases)


if __name__ == "__main__":
    unittest.main()
