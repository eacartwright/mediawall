"""
Tests for folder scanning. No Qt required.

Run from the project folder:  python -m unittest
"""

import os
import tempfile
import unittest
from pathlib import Path

from core.media_browser import (
    MediaBrowser, animation_duration_ms, file_patterns, format_duration, is_animated, media_type_for,
    neighbour_file,
)


def _gif_bytes(delays):
    """A minimal GIF: a global color table, then one 1x1 frame per delay (in 1/100 s)."""
    data = b"GIF89a" + (1).to_bytes(2, "little") * 2 + bytes([0x80, 0, 0]) + bytes(6)
    data += bytes([0x21, 0xFF, 11]) + b"NETSCAPE2.0" + bytes([3, 1, 0, 0, 0])   # looping
    for delay in delays:
        data += bytes([0x21, 0xF9, 4, 0]) + delay.to_bytes(2, "little") + bytes([0, 0])
        data += bytes([0x2C]) + bytes(4) + (1).to_bytes(2, "little") * 2 + bytes([0, 2, 2, 0x44, 1, 0])
    return data + bytes([0x3B])


def _webp_bytes(durations, odd_chunk=False):
    """A minimal animated WebP's chunks: only what the duration needs."""
    chunks = b"VP8X" + (10).to_bytes(4, "little") + bytes([0x02]) + bytes(9)
    if odd_chunk:
        chunks += b"EXIF" + (3).to_bytes(4, "little") + b"abc" + bytes(1)
    for ms in durations:
        payload = bytes(12) + ms.to_bytes(3, "little") + bytes(1) + b"frame!"
        chunks += b"ANMF" + len(payload).to_bytes(4, "little") + payload
    return b"RIFF" + (len(chunks) + 4).to_bytes(4, "little") + b"WEBP" + chunks


class MediaTypeTests(unittest.TestCase):

    def test_webm_is_a_video(self):
        self.assertEqual(media_type_for("clip.webm"), "video")
        self.assertEqual(media_type_for("CLIP.WEBM"), "video")
        self.assertIn("*.webm", file_patterns("video"))


class AnimationDurationTests(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def duration(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return animation_duration_ms(path)

    def test_gif_adds_up_its_frames(self):
        self.assertEqual(self.duration("a.gif", _gif_bytes([10, 20, 5])), 350)

    def test_gif_too_short_a_delay_counts_as_100_ms(self):
        self.assertEqual(self.duration("a.gif", _gif_bytes([0, 1, 2])), 220)

    def test_webp_adds_up_its_frames(self):
        self.assertEqual(self.duration("a.webp", _webp_bytes([40, 60, 100])), 200)

    def test_webp_with_an_odd_sized_chunk(self):
        self.assertEqual(self.duration("a.webp", _webp_bytes([40], odd_chunk=True)), 40)

    def test_not_animated_or_damaged_is_zero(self):
        self.assertEqual(self.duration("a.gif", b"not a gif at all"), 0)
        self.assertEqual(self.duration("a.webp", b"not a webp"), 0)
        self.assertEqual(self.duration("a.jpg", _gif_bytes([10])), 0)
        self.assertEqual(self.duration("cut.gif", _gif_bytes([10, 10])[:46]), 100)
        self.assertEqual(animation_duration_ms(self.dir / "gone.gif"), 0)


class FormatDurationTests(unittest.TestCase):

    def test_formats(self):
        self.assertEqual(format_duration(0), "")
        self.assertEqual(format_duration(120), "0:01")
        self.assertEqual(format_duration(4400), "0:04")
        self.assertEqual(format_duration(90_000), "1:30")
        self.assertEqual(format_duration(3_723_000), "1:02:03")


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
            ("clip.mp4", b""),
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
        # Everything that moves: animated images and videos.
        names = [e["name"] for e in MediaBrowser().scan_folder(str(self.root), False, "animated")]
        self.assertEqual(sorted(names), ["clip.mp4", "moving.gif", "moving.webp"])

    def test_type_filter(self):
        names = [e["name"] for e in MediaBrowser().scan_folder(str(self.root), False, "image")]
        self.assertEqual(len(names), 7)


class NeighbourFileTests(unittest.TestCase):
    """An audio track's Continue Play and previous/next."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("b.mp3", "a.mp3", "c.m4a", "photo.jpg", "clip.mp4"):
            (self.root / name).write_bytes(b"")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "z.mp3").write_bytes(b"")

    def tearDown(self):
        self.tmp.cleanup()

    def name(self, path):
        return Path(path).name if path else None

    def test_steps_by_name_among_the_same_type_and_goes_round(self):
        self.assertEqual(self.name(neighbour_file(self.root / "a.mp3", 1)), "b.mp3")
        self.assertEqual(self.name(neighbour_file(self.root / "c.m4a", 1)), "a.mp3")
        self.assertEqual(self.name(neighbour_file(self.root / "a.mp3", -1)), "c.m4a")

    def test_a_file_no_longer_there_starts_over(self):
        self.assertEqual(self.name(neighbour_file(self.root / "gone.mp3", 1)), "a.mp3")

    def test_no_folder(self):
        self.assertIsNone(neighbour_file(self.root / "nowhere" / "x.mp3", 1))


class FilePatternTests(unittest.TestCase):
    """Add File…'s dialog filters."""

    def test_every_supported_file_in_both_cases(self):
        patterns = file_patterns()
        for p in ("*.jpg", "*.JPG", "*.mp4", "*.MP4", "*.mp3", "*.M4A", "*.webp"):
            self.assertIn(p, patterns)

    def test_one_type(self):
        self.assertIn("*.wav", file_patterns("audio"))
        self.assertNotIn("*.jpg", file_patterns("audio"))


if __name__ == "__main__":
    unittest.main()
