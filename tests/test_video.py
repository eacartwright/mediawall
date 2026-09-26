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

    def test_speed_and_pitch(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.assertEqual((media.speed, media.preserve_pitch), (1.0, False))
        self.scene.set_media_option(media.id, "speed", 10)
        self.assertEqual(media.speed, 4.0)                      # clamped
        self.scene.set_media_option(media.id, "speed", 0.1)
        self.assertEqual(media.speed, 0.25)
        self.assertTrue(self.scene.set_media_option(media.id, "preserve_pitch", True))

    def test_loop_points(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.assertEqual((media.loop_a, media.loop_b), (-1.0, -1.0))

        self.assertTrue(self.scene.set_loop(media.id, 5000, -1))    # A only
        self.assertEqual((media.loop_a, media.loop_b), (5000, -1))

        self.assertTrue(self.scene.set_loop(media.id, 5000, 2000))  # B before A
        self.assertEqual((media.loop_a, media.loop_b), (2000, 5000))

        self.assertFalse(self.scene.set_loop(media.id, 2000, 2050)) # too close
        self.assertEqual((media.loop_a, media.loop_b), (2000, 5000))

        self.assertTrue(self.scene.set_loop(media.id, -1, -1))      # clear
        self.assertEqual((media.loop_a, media.loop_b), (-1.0, -1.0))

    def test_playback_options_saved_and_sanitized(self):
        from core.project import scene_from_dict, scene_to_dict

        media = self.scene.add_media(self.src.id, 0, 0)
        self.scene.set_media_option(media.id, "speed", 1.5)
        self.scene.set_media_option(media.id, "preserve_pitch", True)
        self.scene.set_loop(media.id, 1000, 3000)

        data = scene_to_dict(self.scene)
        loaded, warnings = scene_from_dict(data)
        m = loaded.get(media.id)
        self.assertEqual((m.speed, m.preserve_pitch, m.loop_a, m.loop_b),
                         (1.5, True, 1000, 3000))
        self.assertEqual(warnings, [])

        # Hand-edited nonsense is repaired on load.
        raw = next(o for o in data["objects"] if o["id"] == media.id)
        raw.update(speed=99.0, loop_a=3000.0, loop_b=3010.0)
        m = scene_from_dict(data)[0].get(media.id)
        self.assertEqual((m.speed, m.loop_a, m.loop_b), (4.0, -1.0, -1.0))



class AudioTrackTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.src = self.scene.add_source("/music/song.m4a", "audio")
        self.box = self.scene.add_object("container", 0, 0)

    def test_track_defaults(self):
        track = self.scene.add_audio_track(self.src.id)
        self.assertEqual(track.type, "audio")
        self.assertFalse(track.muted)          # unlike canvas videos
        self.assertTrue(track.loop)
        self.assertTrue(track.playing)
        self.assertEqual(self.scene.display_name(track.id), "song.m4a")

    def test_track_is_not_on_the_canvas(self):
        track = self.scene.add_audio_track(self.src.id)
        self.assertNotIn(track, self.scene.layer_order())
        self.assertFalse(self.scene.bring_to_front(track.id))
        self.assertFalse(self.scene.send_backward(track.id))
        self.assertTrue(self.scene.is_at_front(track.id))
        self.assertEqual(track.z, 0)
        # Other objects' stacking ignores it.
        self.assertTrue(self.scene.is_at_front(self.box.id))

    def test_track_playback_settings(self):
        track = self.scene.add_audio_track(self.src.id)
        self.assertTrue(self.scene.set_media_option(track.id, "volume", 0.4))
        self.assertTrue(self.scene.set_media_option(track.id, "speed", 0.5))
        self.assertTrue(self.scene.set_loop(track.id, 1000, 4000))
        self.assertTrue(self.scene.set_playing(track.id, False))

    def test_convert_free_video_to_track(self):
        vid = self.scene.add_source("/v/clip.mp4", "video", 1920, 1080)
        media = self.scene.add_media(vid.id, 10, 10)
        self.scene.set_media_option(media.id, "speed", 1.5)
        self.scene.set_loop(media.id, 1000, 5000)

        track = self.scene.convert_to_audio_track(media.id)

        self.assertIsNone(self.scene.get(media.id))              # off the canvas
        self.assertIs(self.scene.get(track.id), track)
        self.assertNotEqual(track.id, media.id)                  # new id (clean undo)
        self.assertEqual((track.type, track.source_id, track.muted),
                         ("audio", vid.id, False))
        self.assertEqual((track.speed, track.loop_a, track.loop_b), (1.5, 1000, 5000))
        self.assertNotIn(track, self.scene.layer_order())

    def test_convert_container_content_to_track(self):
        vid = self.scene.add_source("/v/clip.mp4", "video", 1920, 1080)
        content, _ = self.scene.add_media_to_container(vid.id, self.box.id)

        track = self.scene.convert_to_audio_track(content.id)

        self.assertIsNone(self.scene.content_of(self.box.id))   # container emptied
        self.assertIsNone(track.parent_id)
        self.assertIn(self.box, self.scene.layer_order())

    def test_only_videos_convert(self):
        img = self.scene.add_source("/p/photo.jpg", "image", 400, 300)
        photo = self.scene.add_media(img.id, 0, 0)
        self.assertFalse(self.scene.can_convert_to_audio(photo.id))
        self.assertIsNone(self.scene.convert_to_audio_track(photo.id))

    def test_track_saved_and_loaded(self):
        from core.project import scene_from_dict, scene_to_dict

        track = self.scene.add_audio_track(self.src.id)
        self.scene.set_media_option(track.id, "volume", 0.4)

        loaded, warnings = scene_from_dict(scene_to_dict(self.scene))
        t = loaded.get(track.id)
        self.assertEqual(warnings, [])
        self.assertEqual((t.type, t.source_id, t.volume, t.muted),
                         ("audio", self.src.id, 0.4, False))
        self.assertIn(self.src.id, loaded.sources)


if __name__ == "__main__":
    unittest.main()
