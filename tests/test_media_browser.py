"""
Tests for folder scanning. No Qt required.

Run from the project folder:  python -m unittest
"""

import tempfile
import unittest
from pathlib import Path

from core.media_browser import MediaBrowser


class MediaBrowserTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)

        for rel in [
            "top.jpg",
            "notes.txt",
            "Japan/IMG_10.jpg",
            "Japan/IMG_2.jpg",
            "Japan/Kyoto/temple.png",
            "Beach/clip.mp4",
            ".hidden/secret.jpg",
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        self.root = root
        self.browser = MediaBrowser()

    def tearDown(self):
        self.tmp.cleanup()

    def relpaths(self, recursive):
        return [e["relpath"]
                for e in self.browser.scan_folder(str(self.root), recursive)]

    def test_non_recursive_only_top_level(self):
        self.assertEqual(self.relpaths(False), ["top.jpg"])

    def test_recursive_order_and_filtering(self):
        self.assertEqual(self.relpaths(True), [
            "top.jpg",                  # chosen folder first
            "Beach/clip.mp4",
            "Japan/IMG_2.jpg",          # natural sort: 2 before 10
            "Japan/IMG_10.jpg",
            "Japan/Kyoto/temple.png",   # subfolder after its parent's files
        ])

    def test_missing_folder_returns_empty(self):
        self.assertEqual(
            self.browser.scan_folder(str(self.root / "nope"), True), []
        )


if __name__ == "__main__":
    unittest.main()
