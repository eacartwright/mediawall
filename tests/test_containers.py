"""
Tests for containers in the scene core. No Qt required.

Run from the project folder:  python -m unittest
"""

import tempfile
import unittest
from pathlib import Path

from core.project import load_project, save_project, scene_from_dict, FORMAT
from core.scene import FIT_CONTAIN, FIT_COVER, Scene, fitted_size


class FittedSizeTests(unittest.TestCase):

    def test_cover_and_contain(self):
        # 2:1 image into a square box
        self.assertEqual(fitted_size(100, 100, 2.0, FIT_CONTAIN), (100, 50))
        self.assertEqual(fitted_size(100, 100, 2.0, FIT_COVER), (200, 100))
        # 1:2 image into a square box
        self.assertEqual(fitted_size(100, 100, 0.5, FIT_CONTAIN), (50, 100))
        self.assertEqual(fitted_size(100, 100, 0.5, FIT_COVER), (100, 200))


class ContainerTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.src = self.scene.add_source("/pics/wide.jpg", "image", 400, 200)
        self.box = self.scene.add_object("container", 100, 100)   # 360 x 260

    def test_add_media_fills_container(self):
        content, released = self.scene.add_media_to_container(
            self.src.id, self.box.id
        )
        self.assertIsNone(released)
        self.assertEqual(content.parent_id, self.box.id)
        # 2:1 into 360x260, cover: height matches, width overflows
        self.assertAlmostEqual(content.height, 260)
        self.assertAlmostEqual(content.width, 520)
        # centered
        self.assertAlmostEqual(content.x, (360 - 520) / 2)
        self.assertAlmostEqual(content.y, 0)

    def test_content_is_not_top_level_or_stacked(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.assertNotIn(content, self.scene.top_level())
        self.assertEqual(content.z, 0)
        self.assertFalse(self.scene.bring_to_front(content.id))

    def test_move_free_media_in_keeps_instance(self):
        media = self.scene.add_media(self.src.id, 0, 0)
        self.scene.set_playing(media.id, False)

        moved, released = self.scene.move_into_container(media.id, self.box.id)

        self.assertTrue(moved)
        self.assertIsNone(released)
        self.assertIs(self.scene.content_of(self.box.id), media)
        self.assertFalse(media.playing)     # state carried over

    def test_replacing_content_releases_old_one(self):
        first, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        second, released = self.scene.add_media_to_container(
            self.src.id, self.box.id
        )
        self.assertIs(released, first)
        self.assertIsNone(first.parent_id)
        self.assertIs(self.scene.content_of(self.box.id), second)

    def test_release_keeps_visual_position(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.fit_content(self.box.id, FIT_CONTAIN)    # 360 x 180, centered

        released = self.scene.release_content(self.box.id)

        # Container at (100,100) size 360x260: content centered at (280, 230)
        self.assertIsNone(released.parent_id)
        self.assertAlmostEqual(released.x + released.width / 2, 280)
        self.assertAlmostEqual(released.y + released.height / 2, 230)
        self.assertAlmostEqual(released.width, 360)
        self.assertIn(released, self.scene.top_level())

    def test_release_accounts_for_rotation(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        # Put content's center 50px right of the container's center.
        self.scene.set_content_geometry(
            self.box.id, content.x + 50, content.y,
            content.width, content.height, 10,
        )
        self.scene.set_geometry(self.box.id, 100, 100, 360, 260, 90)

        released = self.scene.release_content(self.box.id)

        # Rotating the container 90° turns "50px right" into "50px down".
        self.assertAlmostEqual(released.x + released.width / 2, 280)
        self.assertAlmostEqual(released.y + released.height / 2, 280)
        self.assertAlmostEqual(released.rotation, 100)

    def test_locked_resize_scales_content(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        w0, h0 = content.width, content.height

        self.scene.set_geometry(self.box.id, 100, 100, 720, 520, 0)   # 2x

        self.assertAlmostEqual(content.width, w0 * 2)
        self.assertAlmostEqual(content.height, h0 * 2)

    def test_unlocked_resize_leaves_content(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.set_lock_content(self.box.id, False)
        before = (content.x, content.y, content.width, content.height)

        self.scene.set_geometry(self.box.id, 100, 100, 720, 520, 0)

        self.assertEqual(
            (content.x, content.y, content.width, content.height), before
        )

    def _content_scene_center(self, box, content):
        import math
        lx = content.x + content.width / 2 - box.width / 2
        ly = content.y + content.height / 2 - box.height / 2
        r = math.radians(box.rotation)
        cx, cy = box.center
        return (cx + lx * math.cos(r) - ly * math.sin(r),
                cy + lx * math.sin(r) + ly * math.cos(r))

    def test_unlocked_top_left_resize_crops_in_place(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.set_lock_content(self.box.id, False)
        before = self._content_scene_center(self.box, content)
        size = (content.width, content.height)

        # Drag the top-left corner in by (50, 30).
        self.scene.set_geometry(self.box.id, 150, 130, 310, 230, 0)

        after = self._content_scene_center(self.box, content)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])
        self.assertEqual((content.width, content.height), size)

    def test_unlocked_resize_of_rotated_container_crops_in_place(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.set_lock_content(self.box.id, False)
        self.scene.set_geometry(self.box.id, 100, 100, 360, 260, 35)
        before = self._content_scene_center(self.box, content)

        self.scene.set_geometry(self.box.id, 120, 90, 300, 200, 35)

        after = self._content_scene_center(self.box, content)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])

    def test_moving_unlocked_container_carries_content(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.set_lock_content(self.box.id, False)
        local = (content.x, content.y)
        self.scene.set_geometry(self.box.id, 400, 400, 360, 260, 0)
        self.assertEqual((content.x, content.y), local)

    def test_deleting_container_deletes_content(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.remove_object(self.box.id)
        self.assertIsNone(self.scene.get(content.id))

    def test_container_at_respects_rotation_and_z(self):
        # 360x260 box at (100,100) rotated 90° covers x 150..410, y 50..410
        self.scene.set_geometry(self.box.id, 100, 100, 360, 260, 90)
        self.assertIsNotNone(self.scene.container_at(280, 60))
        self.assertIsNone(self.scene.container_at(120, 230))

        top = self.scene.add_object("container", 200, 200)
        self.assertIs(self.scene.container_at(280, 280), top)


class WrapTests(unittest.TestCase):

    def test_wrap_keeps_appearance_and_stacking(self):
        scene = Scene()
        src = scene.add_source("/pics/a.jpg", "image", 400, 200)
        below = scene.add_object("container", 0, 0)
        media = scene.add_media(src.id, 50, 60)
        scene.set_geometry(media.id, 50, 60, 300, 150, 30)
        above = scene.add_object("browser", 0, 0)
        scene.select(media.id)

        box = scene.wrap_in_container(media.id)

        self.assertEqual((box.x, box.y, box.width, box.height, box.rotation),
                         (50, 60, 300, 150, 30))
        self.assertFalse(box.lock_content)     # crop mode: frame edges crop
        self.assertIs(scene.content_of(box.id), media)
        self.assertEqual((media.x, media.y, media.width, media.height,
                          media.rotation), (0, 0, 300, 150, 0))
        # Takes the image's place in the stack
        self.assertEqual([o.id for o in scene._by_z()],
                         [below.id, box.id, above.id])
        self.assertEqual(scene.selected_id, box.id)

    def test_wrap_then_release_round_trips(self):
        scene = Scene()
        src = scene.add_source("/pics/a.jpg", "image", 400, 200)
        media = scene.add_media(src.id, 50, 60)
        scene.set_geometry(media.id, 50, 60, 300, 150, 30)

        box = scene.wrap_in_container(media.id)
        released = scene.release_content(box.id)

        self.assertAlmostEqual(released.x, 50)
        self.assertAlmostEqual(released.y, 60)
        self.assertAlmostEqual(released.rotation, 30)


class ContainerProjectTests(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / "a.jpg"
            photo.write_bytes(b"x")

            scene = Scene()
            src = scene.add_source(str(photo), "image", 400, 200)
            box = scene.add_object("container", 10, 10)
            scene.set_lock_content(box.id, False)
            content, _ = scene.add_media_to_container(src.id, box.id)
            scene.set_content_geometry(box.id, -40, 5, 600, 300, 12)

            path = Path(tmp) / "p.mediawall"
            save_project(scene, path)
            loaded, warnings = load_project(path)

            self.assertEqual(warnings, [])
            lc = loaded.content_of(box.id)
            self.assertIsNotNone(lc)
            self.assertEqual(lc.id, content.id)
            self.assertEqual((lc.x, lc.y, lc.width, lc.height, lc.rotation),
                             (-40, 5, 600, 300, 12))
            self.assertFalse(loaded.get(box.id).lock_content)

    def test_orphaned_content_becomes_free(self):
        data = {
            "format": FORMAT, "version": 1,
            "media_sources": {"s": {"path": "/x.jpg", "type": "image"}},
            "objects": [
                {"id": "m", "type": "media", "source_id": "s",
                 "parent_id": "nope"},
            ],
        }
        scene, warnings = scene_from_dict(data)
        self.assertIsNone(scene.get("m").parent_id)
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
