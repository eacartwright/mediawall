"""
Tests for video-related scene logic. No Qt required.

Run from the project folder:  python -m unittest
"""

import unittest

from core.scene import FALLBACK_ASPECT, Scene


class VideoSceneTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        # Videos are registered without a size; the player reports it later.
        self.src = self.scene.add_source("/v/portrait.mp4", "video")

    def test_placeholder_then_real_size(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.assertTrue(media.pending_size)
        self.assertAlmostEqual(media.width / media.height, FALLBACK_ASPECT)

        changed = self.scene.set_source_size(self.src.id, 180, 320)

        self.assertEqual(changed, [media.id])
        self.assertFalse(media.pending_size)
        self.assertAlmostEqual(media.width / media.height, 180 / 320)

    def test_resized_object_is_not_resized_again(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.scene.set_source_size(self.src.id, 180, 320)
        self.scene.set_geometry(media.id, 0, 0, 100, 100, 0)   # user's choice

        self.scene.set_source_size(self.src.id, 360, 640)      # same aspect, new report
        self.assertEqual((media.width, media.height), (100, 100))

    def test_content_is_reframed_when_size_arrives(self):
        box = self.scene.add_object("container", 0, 0)          # 360 x 260
        content, _ = self.scene.add_media_to_container(self.src.id, box.id)

        changed = self.scene.set_source_size(self.src.id, 180, 320)

        self.assertEqual(changed, [box.id])
        # cover-fit a 9:16 video into 360x260: width matches, height overflows
        self.assertAlmostEqual(content.width, 360)
        self.assertAlmostEqual(content.height, 640)

    def test_video_defaults(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.assertTrue(media.playing)
        self.assertTrue(media.muted)
        self.assertTrue(media.loop)
        self.assertEqual(media.volume, 1.0)

    def test_media_options(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.assertTrue(self.scene.set_media_option(media.id, "muted", False))
        self.assertFalse(self.scene.set_media_option(media.id, "muted", False))
        self.scene.set_media_option(media.id, "volume", 7)
        self.assertEqual(media.volume, 1.0)                     # clamped
        self.assertFalse(self.scene.set_media_option(media.id, "rotation", 5))


if __name__ == "__main__":
    unittest.main()
