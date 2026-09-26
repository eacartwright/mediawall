"""
Tests for undo history saved between sessions. No Qt required.

Run from the project folder:  python -m unittest
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.history import History, snapshot
from core.history_file import (
    MAX_SAVED_STEPS, history_path, load_history, save_history,
)
from core.project import (
    project_file_fingerprint, save_project, scene_to_dict,
)
from core.scene import Scene


class HistoryFileTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name) / "japan.mediawall"

        # A scene with a few recorded changes: add three containers.
        self.scene = Scene()
        self.history = History()
        for i in range(3):
            before = snapshot(self.scene)
            self.scene.add_object("container", i * 10, 0)
            self.history.record(before, now=float(i * 10))

    def tearDown(self):
        self._tmp.cleanup()

    def save_both(self):
        fp = save_project(self.scene, self.project)
        save_history(self.project, self.history, fp)

    def test_file_name(self):
        self.assertEqual(history_path(self.project).name, "japan.mediawall.history")

    def test_round_trip(self):
        self.save_both()
        loaded, note = load_history(self.project, project_file_fingerprint(self.project))

        self.assertEqual(note, "")
        undo, redo = loaded.steps()
        self.assertEqual([len(s.objects) for s in undo], [0, 1, 2])
        self.assertEqual(redo, [])
        # Same content as what was recorded.
        self.assertEqual([scene_to_dict(s) for s in undo],
                         [scene_to_dict(s) for s in self.history.steps()[0]])

    def test_undo_continues_after_reopening(self):
        self.save_both()
        loaded, _ = load_history(self.project, project_file_fingerprint(self.project))
        previous = loaded.undo(snapshot(self.scene))
        self.assertEqual(len(previous.objects), 2)
        self.assertTrue(loaded.can_redo)

    def test_capped(self):
        for i in range(MAX_SAVED_STEPS + 10):
            before = snapshot(self.scene)
            self.scene.add_object("container", 0, 0)
            self.history.record(before, now=1000.0 + i * 10)
        self.save_both()

        loaded, _ = load_history(self.project, project_file_fingerprint(self.project))
        self.assertEqual(len(loaded.steps()[0]), MAX_SAVED_STEPS)

    def test_ignored_if_project_changed_since(self):
        self.save_both()
        self.scene.add_object("browser", 0, 0)
        save_project(self.scene, self.project)       # saved without its history

        loaded, note = load_history(self.project, project_file_fingerprint(self.project))
        self.assertIsNone(loaded)
        self.assertIn("doesn't match", note)

    def test_damaged_history_is_ignored(self):
        self.save_both()
        path = history_path(self.project)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["undo"][1] = "garbage"
        path.write_text(json.dumps(data), encoding="utf-8")

        loaded, note = load_history(self.project, project_file_fingerprint(self.project))
        self.assertIsNone(loaded)
        self.assertIn("damaged", note)

    def test_no_file_no_note(self):
        save_project(self.scene, self.project)
        loaded, note = load_history(self.project, project_file_fingerprint(self.project))
        self.assertIsNone(loaded)
        self.assertEqual(note, "")

    def test_empty_history_removes_the_file(self):
        self.save_both()
        self.assertTrue(history_path(self.project).exists())
        save_history(self.project, History(), save_project(self.scene, self.project))
        self.assertFalse(history_path(self.project).exists())


if __name__ == "__main__":
    unittest.main()
