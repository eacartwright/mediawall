"""
Tests for project save/load. No Qt required.

Run from the project folder:  python -m unittest
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.project import (
    FORMAT, ProjectError, load_project, save_project, scene_from_dict,
)
from core.scene import Scene


class ProjectTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

        self.media_dir = self.dir / "media"
        self.media_dir.mkdir()
        self.photo = self.media_dir / "photo.jpg"
        self.photo.write_bytes(b"not really a jpeg")

        self.project = self.dir / "wall.mediawall"

    def tearDown(self):
        self.tmp.cleanup()

    def build_scene(self):
        scene = Scene()
        src = scene.add_source(str(self.photo), "image", 400, 200)
        a = scene.add_media(src.id, 10, 20)
        b = scene.add_media(src.id, 300, 40)      # second instance, same source
        scene.set_geometry(b.id, 300, 40, 150, 75, 25)
        scene.set_playing(b.id, False)
        br = scene.add_object("browser", 50, 60)
        scene.set_browser_state(br.id, str(self.media_dir), 3)
        scene.set_browser_subfolders(br.id, False)
        c = scene.add_object("container", 5, 5)
        scene.send_to_back(c.id)
        return scene, a, b, br, c

    # ---------------------------------------------

    def test_round_trip(self):
        scene, a, b, br, c = self.build_scene()
        save_project(scene, self.project)

        loaded, warnings = load_project(self.project)
        self.assertEqual(warnings, [])

        # Same objects, same stacking order
        self.assertEqual(
            [o.id for o in loaded._by_z()], [o.id for o in scene._by_z()]
        )

        lb = loaded.get(b.id)
        self.assertEqual((lb.x, lb.y, lb.width, lb.height, lb.rotation),
                         (300, 40, 150, 75, 25))
        self.assertFalse(lb.playing)

        lbr = loaded.get(br.id)
        self.assertEqual(lbr.folder, str(self.media_dir))
        self.assertEqual(lbr.current_index, 3)
        self.assertFalse(lbr.include_subfolders)

        # Two instances still share one source
        self.assertEqual(len(loaded.sources), 1)
        self.assertEqual(loaded.get(a.id).source_id, lb.source_id)

    def test_unused_sources_not_saved(self):
        scene, a, b, br, c = self.build_scene()
        scene.add_source(str(self.dir / "unused.jpg"), "image")
        save_project(scene, self.project)

        data = json.loads(self.project.read_text(encoding="utf-8"))
        self.assertEqual(len(data["media_sources"]), 1)

    def test_missing_file_keeps_object(self):
        scene, a, *_ = self.build_scene()
        save_project(scene, self.project)
        self.photo.unlink()

        loaded, warnings = load_project(self.project)

        self.assertIsNotNone(loaded.get(a.id))
        source = loaded.sources[loaded.get(a.id).source_id]
        self.assertTrue(source.missing)
        self.assertEqual(source.path, str(self.photo))  # path not discarded

    def test_relative_path_finds_moved_folder(self):
        scene, a, *_ = self.build_scene()
        save_project(scene, self.project)

        # Move the project and its media together.
        moved = self.dir / "moved"
        moved.mkdir()
        (self.media_dir).rename(moved / "media")
        self.project.rename(moved / "wall.mediawall")

        loaded, _ = load_project(moved / "wall.mediawall")
        source = loaded.sources[loaded.get(a.id).source_id]

        self.assertFalse(source.missing)
        self.assertEqual(Path(source.path), (moved / "media" / "photo.jpg").resolve())
        self.assertEqual(source.original_path, str(self.photo))

    def test_tolerant_loading(self):
        data = {
            "format": FORMAT,
            "version": 1,
            "media_sources": {},
            "objects": [
                {"id": "x", "type": "hologram"},                  # unknown type
                {"id": "c1", "type": "container", "x": "oops"},   # bad value
                {"id": "c1", "type": "container"},                # duplicate id
                "garbage",
            ],
        }
        scene, warnings = scene_from_dict(data)

        self.assertEqual(len(scene.objects), 2)
        self.assertEqual(len({o.id for o in scene.objects}), 2)
        self.assertEqual(scene.objects[0].x, 0.0)
        self.assertGreaterEqual(len(warnings), 3)

    def test_not_a_project(self):
        self.project.write_text('{"hello": "world"}', encoding="utf-8")
        with self.assertRaises(ProjectError):
            load_project(self.project)

        self.project.write_text("{ broken json", encoding="utf-8")
        with self.assertRaises(ProjectError):
            load_project(self.project)

    def test_newer_version_rejected(self):
        with self.assertRaises(ProjectError):
            scene_from_dict({"format": FORMAT, "version": 999})

    def test_save_leaves_no_temp_files(self):
        scene, *_ = self.build_scene()
        save_project(scene, self.project)
        save_project(scene, self.project)
        leftovers = [p for p in self.dir.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(leftovers, [])

    def test_unchanged_geometry_is_not_a_change(self):
        scene, a, *_ = self.build_scene()
        self.assertFalse(
            scene.set_geometry(a.id, a.x, a.y, a.width, a.height, a.rotation)
        )


if __name__ == "__main__":
    unittest.main()
