import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cleaner  # noqa: E402


class CleanerTests(unittest.TestCase):
    def test_scan_and_clean_only_contents(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "cache"
            (root / "sub").mkdir(parents=True)
            (root / "a.bin").write_bytes(b"x" * 1000)
            (root / "sub" / "b.bin").write_bytes(b"y" * 500)
            cat = cleaner.Category("t", "t", "t", lambda: [root])
            self.assertEqual(cleaner.scan(cat), 1500)
            freed, errors = cleaner.clean(cat)
            self.assertEqual((freed, errors), (1500, 0))
            self.assertTrue(root.is_dir())                 # Ordner selbst bleibt
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(cleaner.scan(cat), 0)

    def test_missing_paths_are_ignored(self):
        cat = cleaner.Category("t", "t", "t", lambda: [Path("/nonexistent/xyz")])
        self.assertEqual(cleaner.scan(cat), 0)
        self.assertEqual(cleaner.clean(cat), (0, 0))

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "keep"
            target.mkdir()
            (target / "important.txt").write_text("data")
            root = Path(d) / "cache"
            root.mkdir()
            try:
                (root / "link").symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("Symlinks nicht erlaubt")
            cleaner.clean(cleaner.Category("t", "t", "t", lambda: [root]))
            self.assertTrue((target / "important.txt").exists())

    def test_catalog_of_categories(self):
        ids = [c.id for c in cleaner.categories()]
        for must in ("temp_user", "browser", "recycle", "epic_web"):
            self.assertIn(must, ids)


if __name__ == "__main__":
    unittest.main()
