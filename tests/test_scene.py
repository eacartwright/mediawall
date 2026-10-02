"""
Tests for the pure-Python scene core. No Qt required.

Run from the project folder:  python -m unittest
"""

import unittest

from core.scene import Scene


class SceneTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()

    def test_same_path_registers_one_source(self):
        a = self.scene.add_source("/pics/a.jpg", "image", 400, 200)
        b = self.scene.add_source("/pics/a.jpg", "image")
        self.assertIs(a, b)
        self.assertEqual(len(self.scene.sources), 1)

    def test_media_instances_share_a_source(self):
        src = self.scene.add_source("/pics/a.jpg", "image", 400, 200)
        m1 = self.scene.add_media(src.id, 0, 0)
        m2 = self.scene.add_media(src.id, 50, 50)
        self.assertNotEqual(m1.id, m2.id)
        self.assertEqual(m1.source_id, m2.source_id)

    def test_media_sized_to_aspect_ratio(self):
        src = self.scene.add_source("/pics/wide.jpg", "image", 400, 200)
        m = self.scene.add_media(src.id, 0, 0)
        self.assertAlmostEqual(m.width / m.height, 2.0)

    def test_new_objects_go_on_top(self):
        a = self.scene.add_object("browser", 0, 0)
        b = self.scene.add_object("container", 0, 0)
        self.assertGreater(b.z, a.z)

    def test_z_operations(self):
        a = self.scene.add_object("container", 0, 0)
        b = self.scene.add_object("container", 0, 0)
        c = self.scene.add_object("container", 0, 0)

        self.scene.send_to_back(c.id)
        self.assertEqual([o.id for o in self.scene._by_z()], [c.id, a.id, b.id])

        self.scene.bring_forward(c.id)
        self.assertEqual([o.id for o in self.scene._by_z()], [a.id, c.id, b.id])

        self.scene.bring_to_front(a.id)
        self.assertEqual([o.id for o in self.scene._by_z()], [c.id, b.id, a.id])

        self.scene.send_backward(a.id)
        self.assertEqual([o.id for o in self.scene._by_z()], [c.id, a.id, b.id])

        self.assertEqual(sorted(o.z for o in self.scene.objects), [1, 2, 3])

    def test_remove_clears_selection_and_compacts_z(self):
        a = self.scene.add_object("container", 0, 0)
        b = self.scene.add_object("container", 0, 0)
        self.scene.select(a.id)
        self.scene.remove_object(a.id)
        self.assertIsNone(self.scene.selected_id)
        self.assertEqual(b.z, 1)

    def test_select_unknown_id_is_rejected(self):
        self.assertFalse(self.scene.select("nope"))


class MirrorTests(unittest.TestCase):

    def test_mirror_is_saved_and_duplicated(self):
        from core.project import scene_from_dict, scene_to_dict

        scene = Scene()
        src = scene.add_source("/p/a.jpg", "image", 400, 200)
        free = scene.add_media(src.id, 0, 0)
        box = scene.add_object("container", 0, 0)
        inner, _ = scene.add_media_to_container(src.id, box.id)

        self.assertTrue(scene.set_media_option(free.id, "mirrored", True))
        self.assertTrue(scene.set_media_option(inner.id, "mirrored", True))
        self.assertFalse(scene.set_media_option(free.id, "mirrored", True))   # unchanged

        loaded, warnings = scene_from_dict(scene_to_dict(scene))
        self.assertEqual(warnings, [])
        self.assertTrue(loaded.get(free.id).mirrored)
        self.assertTrue(loaded.content_of(box.id).mirrored)

        copy = scene.duplicate_object(free.id)
        self.assertTrue(copy.mirrored)


class LayerTests(unittest.TestCase):
    """Browsers always stack above other objects (their own group)."""

    def setUp(self):
        self.scene = Scene()
        s = self.scene
        self.b1 = s.add_object("browser", 0, 0)
        self.a = s.add_object("container", 0, 0)
        self.b2 = s.add_object("browser", 0, 0)
        self.c = s.add_object("container", 0, 0)

    def order(self):
        return [o.id for o in self.scene.layer_order()]    # top first

    def test_browsers_listed_above_everything(self):
        self.assertEqual(self.order(),
                         [self.b2.id, self.b1.id, self.c.id, self.a.id])

    def test_moves_stay_within_group(self):
        s = self.scene
        # The top ordinary object can't pass the browsers.
        self.assertFalse(s.bring_forward(self.c.id))
        self.assertFalse(s.bring_to_front(self.c.id))
        # The bottom browser can't go below ordinary objects.
        self.assertFalse(s.send_backward(self.b1.id))
        self.assertFalse(s.send_to_back(self.b1.id))
        # Within a group, moves work as usual.
        self.assertTrue(s.bring_to_front(self.a.id))
        self.assertTrue(s.send_backward(self.b2.id))
        self.assertEqual(self.order(),
                         [self.b1.id, self.b2.id, self.a.id, self.c.id])

    def test_front_and_back_are_per_group(self):
        s = self.scene
        self.assertTrue(s.is_at_front(self.c.id))
        self.assertFalse(s.is_at_back(self.c.id))
        self.assertTrue(s.is_at_back(self.a.id))
        self.assertTrue(s.is_at_front(self.b2.id))
        self.assertTrue(s.is_at_back(self.b1.id))

    def test_move_to_layer_position(self):
        s = self.scene
        extra = s.add_object("container", 0, 0)
        # top first: b2, b1, extra, c, a
        self.assertTrue(s.move_to_layer_position(self.a.id, 2))
        self.assertEqual(self.order(),
                         [self.b2.id, self.b1.id, self.a.id, extra.id, self.c.id])
        # Dragged among the browsers: clamped to the top of its group.
        self.assertTrue(s.move_to_layer_position(self.c.id, 0))
        self.assertEqual(self.order()[2], self.c.id)
        # A browser dragged to the bottom stays the lowest browser.
        self.assertTrue(s.move_to_layer_position(self.b2.id, 99))
        self.assertEqual(self.order()[:2], [self.b1.id, self.b2.id])
        # No change, no-op.
        self.assertFalse(s.move_to_layer_position(self.b2.id, 1))
        self.assertEqual(sorted(o.z for o in s.layer_order()), [1, 2, 3, 4, 5])

    def test_display_names(self):
        s = self.scene
        src = s.add_source(r"C:\pics\trip\beach.jpg", "image", 400, 200)
        media = s.add_media(src.id, 0, 0)
        s.add_media_to_container(src.id, self.a.id)
        self.b1.folder = "/home/me/Pictures/Japan/"

        self.assertEqual(s.display_name(media.id), "beach.jpg")
        self.assertEqual(s.display_name(self.a.id), "Container · beach.jpg")
        self.assertEqual(s.display_name(self.c.id), "Container (empty)")
        self.assertEqual(s.display_name(self.b1.id), "Browser · Japan")
        self.assertEqual(s.display_name(self.b2.id), "Browser")


if __name__ == "__main__":
    unittest.main()
