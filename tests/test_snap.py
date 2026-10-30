import unittest

from core.snap import bounding_box, snap_move, snap_resize

WALL = (1920, 1080)


class SnapMoveTests(unittest.TestCase):

    def test_touching_another_object(self):
        other = (100, 100, 300, 300)
        # Left edge 5 px right of the other's right edge: pulled in.
        dx, dy, guides = snap_move((305, 150, 405, 250), [other], None)
        self.assertEqual(dx, -5)
        self.assertEqual(dy, 0)
        self.assertIn((300, 100, 300, 300), guides)

    def test_lining_up_edges_on_both_axes(self):
        other = (100, 100, 300, 300)
        dx, dy, _ = snap_move((103, 497, 203, 597), [other], None)
        self.assertEqual((dx, dy), (-3, 0))        # left to left; nothing near on y
        dx, dy, _ = snap_move((500, 296, 600, 396), [other], None)
        self.assertEqual((dx, dy), (0, 4))         # top to the other's bottom

    def test_wall_edges_and_middle(self):
        dx, dy, _ = snap_move((6, 1000, 106, 1076), [], WALL)
        self.assertEqual((dx, dy), (-6, 4))        # left edge, bottom edge
        dx, _, _ = snap_move((905, 500, 1011, 600), [], WALL)
        self.assertEqual(dx, 2)                    # centered: 958 -> 960

    def test_centers_only_snap_to_centers(self):
        # Center 3 px from the other's left edge: not a snap.
        dx, _, _ = snap_move((-47, 500, 153, 600), [(50, 100, 250, 300)], None)
        self.assertEqual(dx, 0)

    def test_nearest_wins_and_far_is_ignored(self):
        others = [(0, 0, 100, 100), (0, 0, 106, 100)]
        dx, _, _ = snap_move((104, 400, 204, 500), others, None)
        self.assertEqual(dx, 2)
        dx, _, _ = snap_move((120, 400, 220, 500), others, None)
        self.assertEqual(dx, 0)


class SnapResizeTests(unittest.TestCase):

    def test_only_the_dragged_edges_snap(self):
        other = (400, 0, 600, 200)
        dx, dy, gx, gy = snap_resize((100, 100, 395, 300), 1, 0, [other], None)
        self.assertEqual((dx, dy), (5, 0))
        self.assertEqual(gx, [(400, 0, 400, 300)])
        self.assertEqual(gy, [])
        # Dragging the left edge: the right edge near 400 doesn't count.
        dx, _, _, _ = snap_resize((100, 100, 395, 300), -1, 0, [other], None)
        self.assertEqual(dx, 0)

    def test_corner_snaps_both_axes(self):
        dx, dy, gx, gy = snap_resize((100, 100, 1915, 1077), 1, 1, [], WALL)
        self.assertEqual((dx, dy), (5, 3))
        self.assertTrue(gx and gy)


class BoundingBoxTests(unittest.TestCase):

    def test_rotated_quarter_turn(self):
        left, top, right, bottom = bounding_box(0, 0, 200, 100, 90)
        self.assertAlmostEqual(left, 50)
        self.assertAlmostEqual(top, -50)
        self.assertAlmostEqual(right, 150)
        self.assertAlmostEqual(bottom, 150)


if __name__ == "__main__":
    unittest.main()
