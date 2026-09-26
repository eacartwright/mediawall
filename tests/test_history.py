"""
Tests for duplicate, relink, and undo/redo history. No Qt required.

Run from the project folder:  python -m unittest
"""

import tempfile
import unittest
from pathlib import Path

from core.history import History, snapshot
from core.scene import Scene


class DuplicateTests(unittest.TestCase):

    def test_duplicate_media_is_new_instance_of_same_source(self):
        scene = Scene()
        src = scene.add_source("/pics/a.jpg", "image", 400, 200)
        media = scene.add_media(src.id, 10, 10)

        copy = scene.duplicate_object(media.id)

        self.assertNotEqual(copy.id, media.id)
        self.assertEqual(copy.source_id, media.source_id)
        self.assertEqual((copy.x, copy.y), (30, 30))
        self.assertGreater(copy.z, media.z)
        self.assertEqual(len(scene.sources), 1)

    def test_duplicate_container_copies_content(self):
        scene = Scene()
        src = scene.add_source("/pics/a.jpg", "image", 400, 200)
        box = scene.add_object("container", 0, 0)
        content, _ = scene.add_media_to_container(src.id, box.id)

        copy = scene.duplicate_object(box.id)
        copy_content = scene.content_of(copy.id)

        self.assertIsNotNone(copy_content)
        self.assertNotEqual(copy_content.id, content.id)
        self.assertIs(scene.content_of(box.id), content)   # original untouched


class RelinkTests(unittest.TestCase):

    def test_relink_finds_siblings_in_new_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "new"
            new_dir.mkdir()
            for name in ["a.jpg", "b.jpg"]:
                (new_dir / name).write_bytes(b"x")

            scene = Scene()
            a = scene.add_source("/old/a.jpg", "image")
            b = scene.add_source("/old/b.jpg", "image")
            c = scene.add_source("/elsewhere/c.jpg", "image")
            scene.refresh_missing()

            relinked = scene.relink_source(a.id, str(new_dir / "a.jpg"))

            self.assertEqual(set(relinked), {a.id, b.id})
            self.assertFalse(a.missing or b.missing)
            self.assertTrue(c.missing)
            self.assertEqual(a.original_path, str(Path("/old/a.jpg")))


class HistoryTests(unittest.TestCase):

    def test_undo_redo(self):
        scene = Scene()
        history = History()

        before = snapshot(scene)
        box = scene.add_object("container", 0, 0)
        history.record(before, now=0)

        restored = history.undo(snapshot(scene))
        self.assertEqual(restored.objects, [])

        forward = history.redo(restored)
        self.assertEqual([o.id for o in forward.objects], [box.id])

    def test_snapshots_are_independent(self):
        scene = Scene()
        box = scene.add_object("container", 0, 0)
        snap = snapshot(scene)
        box.x = 999
        self.assertEqual(snap.get(box.id).x, 0)

    def test_merge_key_combines_rapid_changes(self):
        history = History()
        s = Scene()
        history.record(snapshot(s), merge_key="zoom", now=0.0)
        history.record(snapshot(s), merge_key="zoom", now=0.3)
        history.record(snapshot(s), merge_key="zoom", now=0.6)
        self.assertEqual(len(history._undo), 1)

        # Too late to merge
        history.record(snapshot(s), merge_key="zoom", now=5.0)
        self.assertEqual(len(history._undo), 2)

        # Different key never merges
        history.record(snapshot(s), merge_key="other", now=5.1)
        self.assertEqual(len(history._undo), 3)

    def test_new_change_clears_redo(self):
        history = History()
        s = Scene()
        history.record(snapshot(s), now=0)
        history.undo(snapshot(s))
        self.assertTrue(history.can_redo)
        history.record(snapshot(s), now=1)
        self.assertFalse(history.can_redo)

    def test_limit(self):
        history = History(max_steps=3)
        for i in range(10):
            history.record(snapshot(Scene()), now=i)
        self.assertEqual(len(history._undo), 3)


if __name__ == "__main__":
    unittest.main()
