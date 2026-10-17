"""
Tests for folder scanning. No Qt required.

Run from the project folder:  python -m unittest
"""

import os
import tempfile
import unittest
from pathlib import Path

from core.media_browser import MediaBrowser, is_animated


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

    def test_favorites_filter_keeps_only_favorites(self):
        paths = [e["path"] for e in self.browser.scan_folder(str(self.root), True)]
        favorites = [paths[0], paths[3]]
        found = self.browser.scan_folder(str(self.root), True, "favorites",
                                         favorites=favorites)
        self.assertEqual([e["path"] for e in found], favorites)
        self.assertEqual(self.browser.scan_folder(str(self.root), True, "favorites"), [])

    def test_entries_record_size(self):
        (self.root / "top.jpg").write_bytes(b"12345")
        sizes = {e["relpath"]: e["size"] for e in self.browser.scan_folder(str(self.root), True)}
        self.assertEqual((sizes["top.jpg"], sizes["Beach/clip.mp4"]), (5, 0))

    def test_missing_folder_returns_empty(self):
        self.assertEqual(
            self.browser.scan_folder(str(self.root / "nope"), True), []
        )

    def sorted_relpaths(self, sort_by, descending=False, seed=""):
        return [e["relpath"] for e in
                self.browser.scan_folder(str(self.root), True, "all", sort_by, descending, seed)]

    def test_sort_by_name_descending_reverses(self):
        self.assertEqual(self.sorted_relpaths("name", True), self.relpaths(True)[::-1])

    def test_sort_by_date_modified(self):
        # Oldest first: give each file a distinct time, against name order.
        for i, rel in enumerate(["Japan/Kyoto/temple.png", "top.jpg", "Beach/clip.mp4",
                                 "Japan/IMG_10.jpg", "Japan/IMG_2.jpg"]):
            os.utime(self.root / rel, (1_000_000 + i, 1_000_000 + i))
        self.assertEqual(self.sorted_relpaths("date"), [
            "Japan/Kyoto/temple.png", "top.jpg", "Beach/clip.mp4",
            "Japan/IMG_10.jpg", "Japan/IMG_2.jpg"])
        self.assertEqual(self.sorted_relpaths("date", True)[0], "Japan/IMG_2.jpg")

    def test_sort_by_type(self):
        # Images (by extension, then name), then videos.
        self.assertEqual(self.sorted_relpaths("type"), [
            "top.jpg", "Japan/IMG_2.jpg", "Japan/IMG_10.jpg",
            "Japan/Kyoto/temple.png", "Beach/clip.mp4"])

    def test_random_order_is_fixed_by_seed(self):
        first = self.sorted_relpaths("random", seed="container-a")
        self.assertEqual(sorted(first), sorted(self.relpaths(True)))
        self.assertEqual(self.sorted_relpaths("random", seed="container-a"), first)
        self.assertEqual(self.sorted_relpaths("random", True, "container-a"), first)  # no direction


def gif_bytes(frames):
    """A tiny GIF with this many 1x1 frames (each with a delay block)."""
    data = b"GIF89a" + bytes([1, 0, 1, 0, 0x80, 0, 0]) + b"\x00\x00\x00\xff\xff\xff"
    data += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"      # loop extension
    for _ in range(frames):
        data += b"\x21\xf9\x04\x04\x0a\x00\x00\x00"               # frame delay
        data += b"\x2c" + bytes(8) + b"\x00"                       # image descriptor
        data += b"\x02\x02\x4c\x01\x00"                           # image data
    return data + b"\x3b"


def webp_bytes(animated):
    flags = 0x02 if animated else 0x00
    chunk = b"VP8X" + (10).to_bytes(4, "little") + bytes([flags]) + bytes(9)
    return b"RIFF" + (4 + len(chunk)).to_bytes(4, "little") + b"WEBP" + chunk


class AnimatedTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, data in [
            ("moving.gif", gif_bytes(3)),
            ("still.gif", gif_bytes(1)),
            ("moving.webp", webp_bytes(True)),
            ("still.webp", webp_bytes(False)),
            ("simple.webp", b"RIFF\x10\x00\x00\x00WEBPVP8 " + bytes(8)),
            ("broken.gif", b"GIF89a\x01"),
            ("photo.jpg", b""),
        ]:
            (self.root / name).write_bytes(data)

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_animated(self):
        for name, expected in [("moving.gif", True), ("still.gif", False),
                               ("moving.webp", True), ("still.webp", False),
                               ("simple.webp", False), ("broken.gif", False),
                               ("photo.jpg", False), ("nope.gif", False)]:
            with self.subTest(name):
                self.assertEqual(is_animated(self.root / name), expected)

    def test_animated_filter(self):
        names = [e["name"] for e in MediaBrowser().scan_folder(str(self.root), False, "animated")]
        self.assertEqual(names, ["moving.gif", "moving.webp"])

    def test_type_filter(self):
        names = [e["name"] for e in MediaBrowser().scan_folder(str(self.root), False, "image")]
        self.assertEqual(len(names), 7)


if __name__ == "__main__":
    unittest.main()
