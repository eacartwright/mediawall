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


if __name__ == "__main__":
    unittest.main()
