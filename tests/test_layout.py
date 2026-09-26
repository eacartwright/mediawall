"""
Tests for layouts (containers only, saved for reuse). No Qt required.

Run from the project folder:  python -m unittest
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.layout import (
    LAYOUT_EXTENSION, add_layout_to_scene, load_layout, save_layout,
    with_layout_extension,
)
from core.project import ProjectError, save_project
from core.scene import FIT_CONTAIN, Scene


class LayoutTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / ("halves" + LAYOUT_EXTENSION)

        s = self.scene = Scene()
        img = s.add_source("/p/a.jpg", "image", 400, 300)
        song = s.add_source("/m/song.m4a", "audio")
        self.left = s.add_object("container", 0, 0, width=960, height=1080)
        self.right = s.add_object("container", 960, 0, width=960, height=1080)
        s.add_media_to_container(img.id, self.left.id)
        s.add_media_to_container(img.id, self.right.id)
        s.fit_content(self.right.id, FIT_CONTAIN)
        s.set_browsing(self.right.id, True, "/p")
        s.add_media(img.id, 100, 100)                     # free media
        s.add_object("browser", 0, 0)
        s.add_audio_track(song.id)

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_containers_are_saved(self):
        save_layout(self.scene, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "mediawall-layout")
        self.assertEqual([o["type"] for o in data["objects"]], ["container", "container"])
        self.assertNotIn("media_sources", data)

    def test_the_wall_is_unchanged(self):
        before = len(self.scene.objects)
        save_layout(self.scene, self.path)
        self.assertEqual(len(self.scene.objects), before)
        self.assertIsNotNone(self.scene.content_of(self.left.id))
        self.assertEqual(self.right.browse_folder, "/p")

    def test_load_keeps_geometry_and_settings_but_no_media(self):
        save_layout(self.scene, self.path)
        layout, warnings = load_layout(self.path)
        self.assertEqual(warnings, [])
        self.assertEqual(len(layout.objects), 2)
        right = layout.get(self.right.id)
        self.assertEqual((right.x, right.width, right.height), (960, 960, 1080))
        self.assertEqual(right.fit_mode, FIT_CONTAIN)
        self.assertTrue(right.browse_mode)
        self.assertEqual(right.browse_folder, "")          # belonged to the old media
        self.assertIsNone(layout.content_of(self.right.id))
        self.assertEqual(layout.sources, {})

    def test_add_to_wall_uses_new_ids_and_stacks_on_top(self):
        save_layout(self.scene, self.path)
        layout, _ = load_layout(self.path)
        wall = Scene()
        existing = wall.add_object("container", 0, 0)
        browser = wall.add_object("browser", 0, 0)

        added = add_layout_to_scene(wall, layout)
        again = add_layout_to_scene(wall, layout)          # twice: no clashes

        ids = [o.id for o in wall.objects]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn(self.left.id, ids)
        order = [o.id for o in wall.layer_order()]         # top first
        self.assertEqual(order[0], browser.id)             # browsers stay on top
        self.assertEqual(order[1:3], [again[1].id, again[0].id])
        self.assertEqual(order[-1], existing.id)
        self.assertEqual(len(added), 2)

    def test_file_name_gets_exactly_one_extension(self):
        for chosen in ["halves", "halves.layout", "halves.mediawall",
                       "halves.mediawall.layout",
                       "Untitled.mediawall.layout.mediawall.layout",   # Windows dialog
                       "halves.MediaWall.Layout"]:
            self.assertEqual(Path(with_layout_extension(chosen)).name.lower(),
                             ("untitled" if chosen.startswith("Untitled") else "halves")
                             + LAYOUT_EXTENSION, chosen)
        self.assertEqual(with_layout_extension("my.trip.layout"), "my.trip" + LAYOUT_EXTENSION)

    def test_project_file_is_not_a_layout(self):
        project = Path(self._tmp.name) / "wall.mediawall"
        save_project(self.scene, project)
        with self.assertRaises(ProjectError) as cm:
            load_layout(project)
        self.assertIn("project, not a layout", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
