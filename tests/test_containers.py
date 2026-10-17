"""
Tests for containers in the scene core. No Qt required.

Run from the project folder:  python -m unittest
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.project import load_project, save_project, scene_from_dict, scene_to_dict, FORMAT
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

    def test_add_media_fits_container(self):
        content, released = self.scene.add_media_to_container(
            self.src.id, self.box.id
        )
        self.assertIsNone(released)
        self.assertEqual(content.parent_id, self.box.id)
        # 2:1 into 360x260, contain (the default): width matches
        self.assertAlmostEqual(content.width, 360)
        self.assertAlmostEqual(content.height, 180)
        # centered
        self.assertAlmostEqual(content.x, 0)
        self.assertAlmostEqual(content.y, (260 - 180) / 2)

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


class NewContainerTests(unittest.TestCase):

    def test_new_container_is_shaped_like_the_image(self):
        scene = Scene()
        src = scene.add_source("/pics/a.jpg", "image", 400, 200)

        box = scene.add_container_with_media(src.id, 50, 60)

        self.assertEqual((box.type, box.x, box.y, box.width, box.height),
                         ("container", 50, 60, 300, 150))
        content = scene.content_of(box.id)
        self.assertEqual(content.source_id, src.id)
        self.assertEqual((content.x, content.y, content.width, content.height),
                         (0, 0, 300, 150))
        self.assertEqual([o.id for o in scene.top_level()], [box.id])

    def test_video_is_reframed_once_its_size_is_known(self):
        scene = Scene()
        src = scene.add_source("/clips/a.mp4", "video", 0, 0)

        box = scene.add_container_with_media(src.id, 0, 0)
        self.assertAlmostEqual(box.height, 300 * 9 / 16)
        self.assertTrue(scene.content_of(box.id).pending_size)

        self.assertIn(box.id, scene.set_source_size(src.id, 1000, 1000))
        self.assertFalse(scene.content_of(box.id).pending_size)


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


class BrowsingContainerTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.wide = self.scene.add_source("/trip/day1/wide.jpg", "image", 400, 200)
        self.tall = self.scene.add_source("/trip/day2/tall.jpg", "image", 200, 400)
        self.box = self.scene.add_object("container", 0, 0)       # 360 x 260

    def test_fit_mode_is_remembered_for_new_content(self):
        self.assertEqual(self.box.fit_mode, FIT_CONTAIN)              # Fit by default
        self.assertTrue(self.scene.fit_content(self.box.id, FIT_COVER))    # empty: mode only
        self.assertTrue(self.scene.fit_content(self.box.id, FIT_CONTAIN))
        content, _ = self.scene.add_media_to_container(self.wide.id, self.box.id)
        # 2:1 into 360x260, contain: width matches
        self.assertAlmostEqual(content.width, 360)
        self.assertAlmostEqual(content.height, 180)

    def test_browse_mode_uses_the_current_files_folder(self):
        self.scene.add_media_to_container(self.wide.id, self.box.id)
        self.assertTrue(self.scene.set_browsing(self.box.id, True))
        self.assertTrue(self.box.browse_mode)
        self.assertEqual(Path(self.box.browse_folder), Path("/trip/day1"))
        self.assertTrue(self.box.browse_subfolders)
        self.assertTrue(self.scene.set_browsing(self.box.id, False))
        self.assertFalse(self.box.browse_mode)

    def test_empty_container_needs_a_folder(self):
        self.assertFalse(self.scene.set_browsing(self.box.id, True))
        self.assertTrue(self.scene.set_browsing(self.box.id, True, "/trip"))
        self.assertEqual(self.box.browse_folder, "/trip")

    def test_showing_another_file_keeps_the_instance(self):
        content, _ = self.scene.add_media_to_container(self.wide.id, self.box.id)
        self.scene.set_playing(content.id, False)
        self.scene.set_media_option(content.id, "volume", 0.3)
        self.scene.set_loop(content.id, 1000, 2000)

        self.assertTrue(self.scene.show_file_in_container(self.box.id, self.tall.id))

        self.assertIs(self.scene.content_of(self.box.id), content)
        self.assertEqual(content.volume, 0.3)                      # settings kept
        self.assertEqual(content.source_id, self.tall.id)
        self.assertTrue(content.playing)                           # each file plays
        self.assertEqual((content.loop_a, content.loop_b), (-1.0, -1.0))
        # 1:2 into 360x260, contain (the default): height matches
        self.assertAlmostEqual(content.width, 130)
        self.assertAlmostEqual(content.height, 260)

    def test_showing_a_file_in_an_empty_container(self):
        self.assertTrue(self.scene.show_file_in_container(self.box.id, self.tall.id))
        self.assertEqual(self.scene.content_of(self.box.id).source_id, self.tall.id)

    def test_browse_state_saved(self):
        self.scene.set_browsing(self.box.id, True, "/trip")
        self.scene.set_browse_subfolders(self.box.id, False)
        self.scene.fit_content(self.box.id, FIT_CONTAIN)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.mediawall"
            save_project(self.scene, path)
            loaded, warnings = load_project(path)
        box = loaded.get(self.box.id)
        self.assertEqual((box.browse_mode, box.browse_folder, box.browse_subfolders,
                          box.fit_mode), (True, "/trip", False, FIT_CONTAIN))

    def test_bad_fit_mode_is_repaired(self):
        data = {
            "format": FORMAT, "version": 1, "media_sources": {},
            "objects": [{"id": "c", "type": "container", "fit_mode": "zoom"}],
        }
        scene, warnings = scene_from_dict(data)
        self.assertEqual(scene.get("c").fit_mode, FIT_CONTAIN)
        self.assertEqual(len(warnings), 1)


class MediaFilterTests(unittest.TestCase):

    def test_allowed_filters_per_type(self):
        scene = Scene()
        browser = scene.add_object("browser", 0, 0)
        box = scene.add_object("container", 0, 0)
        self.assertTrue(scene.set_media_filter(browser.id, "audio"))
        self.assertTrue(scene.set_media_filter(box.id, "video"))
        self.assertFalse(scene.set_media_filter(box.id, "audio"))      # containers show no audio
        self.assertFalse(scene.set_media_filter(box.id, "gifs"))
        self.assertEqual((browser.media_filter, box.media_filter), ("audio", "video"))

    def test_saved_and_repaired(self):
        scene = Scene()
        box = scene.add_object("container", 0, 0)
        scene.set_media_filter(box.id, "image")
        loaded, warnings = scene_from_dict(json.loads(json.dumps(scene_to_dict(scene))))
        self.assertEqual((loaded.get(box.id).media_filter, warnings), ("image", []))

        data = {
            "format": FORMAT, "version": 1, "media_sources": {},
            "objects": [{"id": "c", "type": "container", "media_filter": "audio"}],
        }
        scene, warnings = scene_from_dict(data)
        self.assertEqual(scene.get("c").media_filter, "all")
        self.assertEqual(len(warnings), 1)


class SortAndContinueTests(unittest.TestCase):

    def test_sort_setters(self):
        scene = Scene()
        browser = scene.add_object("browser", 0, 0)
        box = scene.add_object("container", 0, 0)
        text = scene.add_text(0, 0)
        self.assertTrue(scene.set_sort(browser.id, "type", True))
        self.assertFalse(scene.set_sort(browser.id, "type", True))     # no change
        self.assertTrue(scene.set_sort(box.id, descending=True))       # direction only
        self.assertFalse(scene.set_sort(box.id, "size"))
        self.assertFalse(scene.set_sort(text.id, "name", True))
        self.assertEqual((browser.sort_by, browser.sort_descending), ("type", True))
        self.assertEqual((box.sort_by, box.sort_descending), ("name", True))

    def test_continue_play_is_for_containers(self):
        scene = Scene()
        box = scene.add_object("container", 0, 0)
        browser = scene.add_object("browser", 0, 0)
        self.assertTrue(scene.set_continue_play(box.id, True))
        self.assertFalse(scene.set_continue_play(box.id, True))
        self.assertFalse(scene.set_continue_play(browser.id, True))
        self.assertTrue(box.continue_play)


class FillAlongTests(unittest.TestCase):
    """Double-click an edge bar: stretch into the free space (1280 x 800 canvas)."""

    def setUp(self):
        self.scene = Scene()

    def box(self, x, y, w, h, kind="container"):
        return self.scene.add_object(kind, x, y, width=w, height=h)

    def fill(self, obj, axis):
        return self.scene.fill_along(obj.id, axis, 1280, 800)

    def test_alone_fills_the_canvas_height(self):
        b = self.box(100, 300, 200, 100)
        self.assertTrue(self.fill(b, "v"))
        self.assertEqual((b.x, b.y, b.width, b.height), (100, 0, 200, 800))

    def test_stops_at_neighbours_in_its_column(self):
        above = self.box(80, 50, 300, 100)        # overlaps the column
        below = self.box(250, 600, 300, 100)      # overlaps the column
        aside = self.box(600, 0, 300, 800)        # another column: ignored
        b = self.box(100, 300, 200, 100)
        self.fill(b, "v")
        self.assertEqual((b.y, b.height), (150, 450))

    def test_horizontal(self):
        left = self.box(0, 100, 300, 400)
        b = self.box(500, 200, 200, 100)
        self.fill(b, "h")
        self.assertEqual((b.x, b.width), (300, 980))

    def test_browsers_and_overlapping_objects_are_ignored(self):
        self.box(100, 0, 200, 100, "browser")
        self.box(150, 320, 50, 50)                # already overlaps b
        b = self.box(100, 300, 200, 100)
        self.fill(b, "v")
        self.assertEqual((b.y, b.height), (0, 800))

    def test_only_grows(self):
        b = self.box(100, -50, 200, 900)          # already past both edges
        self.assertFalse(self.fill(b, "v"))
        self.assertEqual((b.y, b.height), (-50, 900))

    def test_rotated_objects_are_left_alone(self):
        b = self.box(100, 300, 200, 100)
        b.rotation = 20
        self.assertFalse(self.fill(b, "v"))

    def test_content_follows_the_usual_resize(self):
        src = self.scene.add_source("/p/a.jpg", "image", 400, 200)
        b = self.box(100, 300, 200, 100)
        content, _ = self.scene.add_media_to_container(src.id, b.id)
        self.fill(b, "v")                         # locked: content scales
        self.assertAlmostEqual(content.height, 800)


class ScaleObjectTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.src = self.scene.add_source("/pics/wide.jpg", "image", 400, 200)
        self.box = self.scene.add_object("container", 100, 100)   # 360 x 260

    def test_scales_around_point(self):
        # Around the top-left corner: that corner stays put.
        self.assertTrue(self.scene.scale_object(self.box.id, 100, 100, 2.0))
        b = self.box
        self.assertEqual((b.x, b.y, b.width, b.height), (100, 100, 720, 520))

    def test_rotation_does_not_change_the_center_math(self):
        self.box.rotation = 30
        cx, cy = self.box.center
        self.scene.scale_object(self.box.id, cx, cy, 0.5)
        self.assertEqual(self.box.center, (cx, cy))
        self.assertEqual(self.box.rotation, 30)

    def test_content_scales_with_container_even_unlocked(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.scene.set_lock_content(self.box.id, False)
        self.scene.set_content_geometry(self.box.id, -40, 10, 520, 260, 15)

        self.scene.scale_object(self.box.id, 0, 0, 1.5)

        self.assertEqual(
            (content.x, content.y, content.width, content.height, content.rotation),
            (-60, 15, 780, 390, 15))

    def test_limits(self):
        # 260 is the shorter side; it can't go below SCALE_MIN_SIDE.
        self.scene.scale_object(self.box.id, 0, 0, 0.001)
        self.assertAlmostEqual(self.box.height, 20)
        self.assertFalse(self.scene.scale_object(self.box.id, 0, 0, 0.5))
        # ...but can always grow back.
        self.assertTrue(self.scene.scale_object(self.box.id, 0, 0, 2.0))

    def test_content_cannot_be_scaled_directly(self):
        content, _ = self.scene.add_media_to_container(self.src.id, self.box.id)
        self.assertFalse(self.scene.scale_object(content.id, 0, 0, 2.0))


class LockedContainerTests(unittest.TestCase):
    """Lock Container: nothing about it changes until it is unlocked."""

    def setUp(self):
        self.scene = Scene()
        self.wide = self.scene.add_source("/trip/wide.jpg", "image", 400, 200)
        self.tall = self.scene.add_source("/trip/tall.jpg", "image", 200, 400)
        self.free = self.scene.add_media(self.tall.id, 600, 0)
        self.box = self.scene.add_object("container", 0, 0)
        self.content, _ = self.scene.add_media_to_container(self.wide.id, self.box.id)
        self.assertTrue(self.scene.set_locked(self.box.id, True))
        self.assertFalse(self.scene.set_locked(self.box.id, True))   # no change

    def test_container_cannot_move_resize_rotate_or_scale(self):
        before = (self.box.x, self.box.y, self.box.width, self.box.height, self.box.rotation)
        self.assertFalse(self.scene.set_geometry(self.box.id, 50, 50, 100, 100, 30))
        self.assertFalse(self.scene.scale_object(self.box.id, 0, 0, 2.0))
        self.assertFalse(self.scene.fill_along(self.box.id, "h", 2000, 2000))
        self.assertEqual((self.box.x, self.box.y, self.box.width, self.box.height,
                          self.box.rotation), before)

    def test_content_cannot_change(self):
        frame = (self.content.x, self.content.y, self.content.width, self.content.height)
        self.assertFalse(self.scene.set_content_geometry(self.box.id, 5, 5, 10, 10, 0))
        self.assertFalse(self.scene.fit_content(self.box.id, FIT_COVER))
        self.assertFalse(self.scene.show_file_in_container(self.box.id, self.tall.id))
        self.assertEqual(self.scene.add_media_to_container(self.tall.id, self.box.id), (None, None))
        self.assertEqual(self.scene.move_into_container(self.free.id, self.box.id), (False, None))
        self.assertIsNone(self.scene.release_content(self.box.id))
        self.assertFalse(self.scene.remove_content(self.box.id))
        self.assertFalse(self.scene.set_browsing(self.box.id, True, "/trip"))
        self.assertIs(self.scene.content_of(self.box.id), self.content)
        self.assertEqual(self.content.source_id, self.wide.id)
        self.assertEqual((self.content.x, self.content.y, self.content.width,
                          self.content.height), frame)

    def test_playback_still_works(self):
        self.assertTrue(self.scene.set_media_option(self.content.id, "volume", 0.5))
        self.assertTrue(self.scene.set_playing(self.content.id, False))

    def test_unlocked_it_changes_again(self):
        self.assertTrue(self.scene.set_locked(self.box.id, False))
        self.assertTrue(self.scene.set_geometry(self.box.id, 50, 50, 100, 100, 30))
        self.assertTrue(self.scene.show_file_in_container(self.box.id, self.tall.id))

    def test_lock_is_saved(self):
        loaded, _ = scene_from_dict(scene_to_dict(self.scene))
        self.assertTrue(loaded.get(self.box.id).locked)
        self.assertFalse(loaded.get(self.free.id).locked)


class FavoritesTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.box = self.scene.add_object("container", 0, 0)

    def test_mark_and_unmark(self):
        self.assertTrue(self.scene.set_favorite(self.box.id, "/a.jpg", True))
        self.assertFalse(self.scene.set_favorite(self.box.id, "/a.jpg", True))   # already
        self.assertTrue(self.scene.set_favorite(self.box.id, "/b.jpg", True))
        self.assertEqual(self.box.favorites, ["/a.jpg", "/b.jpg"])
        self.assertTrue(self.scene.set_favorite(self.box.id, "/a.jpg", False))
        self.assertEqual(self.box.favorites, ["/b.jpg"])

    def test_favorites_filter_is_a_container_filter(self):
        self.assertTrue(self.scene.set_media_filter(self.box.id, "favorites"))
        browser = self.scene.add_object("browser", 0, 0)
        self.assertFalse(self.scene.set_media_filter(browser.id, "favorites"))

    def test_saved_with_new_first(self):
        self.scene.set_favorite(self.box.id, "/a.jpg", True)
        self.assertTrue(self.scene.set_new_first(self.box.id, True))
        loaded, warnings = scene_from_dict(scene_to_dict(self.scene))
        box = loaded.get(self.box.id)
        self.assertEqual((box.favorites, box.new_first, warnings), (["/a.jpg"], True, []))

    def test_bad_favorites_are_repaired(self):
        data = {
            "format": FORMAT, "version": 1, "media_sources": {},
            "objects": [{"id": "c", "type": "container", "favorites": ["/a.jpg", 3]},
                        {"id": "d", "type": "container", "favorites": "nope"}],
        }
        scene, warnings = scene_from_dict(data)
        self.assertEqual(scene.get("c").favorites, ["/a.jpg"])
        self.assertEqual(scene.get("d").favorites, [])
        self.assertEqual(len(warnings), 2)


if __name__ == "__main__":
    unittest.main()
