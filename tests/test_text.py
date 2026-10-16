"""
Tests for text objects (readme section 5.4). No Qt required.

Run from the project folder:  python -m unittest
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.history import snapshot
from core.project import load_project, save_project
from core.scene import TEXT_STYLE_DEFAULTS, Scene, normalized_text_style


class TextStyleTests(unittest.TestCase):

    def test_defaults_fill_in_missing_and_bad_values(self):
        style = normalized_text_style({"fill": "red", "bold": "yes", "depth": 12,
                                       "outline": "#abc", "extra": 1})
        self.assertEqual(style["fill"], TEXT_STYLE_DEFAULTS["fill"])     # not a #color
        self.assertEqual(style["bold"], TEXT_STYLE_DEFAULTS["bold"])
        self.assertEqual(style["depth"], 12)
        self.assertEqual(style["outline"], "#abc")
        self.assertNotIn("extra", style)
        self.assertEqual(normalized_text_style(None), TEXT_STYLE_DEFAULTS)

    def test_numbers_are_clamped(self):
        style = normalized_text_style({"outline_width": 99, "depth": -3})
        self.assertEqual((style["outline_width"], style["depth"]), (20.0, 0))

    def test_gradient_end_may_be_empty(self):
        self.assertEqual(normalized_text_style({"fill2": ""})["fill2"], "")
        self.assertEqual(normalized_text_style({"fill2": "#102030"})["fill2"], "#102030")


class TextObjectTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()
        self.text = self.scene.add_text(10, 20, "Hello")

    def test_add_and_name(self):
        self.assertEqual(self.text.type, "text")
        self.assertEqual(self.text.text_style, TEXT_STYLE_DEFAULTS)
        self.assertEqual(self.scene.display_name(self.text.id), "Text · Hello")
        self.assertIn(self.text, self.scene.layer_order())

    def test_set_text_is_one_line(self):
        self.assertTrue(self.scene.set_text(self.text.id, "Two\nlines"))
        self.assertEqual(self.text.text, "Two lines")
        self.assertFalse(self.scene.set_text(self.text.id, "Two lines"))   # no change

    def test_set_style_merges(self):
        self.assertTrue(self.scene.set_text_style(self.text.id, {"depth": 8, "fill": "#ff0000"}))
        self.assertEqual((self.text.text_style["depth"], self.text.text_style["fill"]), (8, "#ff0000"))
        self.assertTrue(self.scene.set_text_style(self.text.id, {"shadow": True}))
        self.assertEqual(self.text.text_style["depth"], 8)                  # kept
        self.assertFalse(self.scene.set_text_style(self.text.id, {"shadow": True}))

    def test_duplicates_dont_share_a_style(self):
        copy = self.scene.duplicate_object(self.text.id)
        self.scene.set_text_style(copy.id, {"italic": True})
        self.assertFalse(self.text.text_style["italic"])

    def test_snapshot_copies_style(self):
        before = snapshot(self.scene)
        self.scene.set_text_style(self.text.id, {"depth": 5})
        self.assertEqual(before.get(self.text.id).text_style["depth"], 0)

    def test_save_and_load(self):
        self.scene.set_text_style(self.text.id, {"fill2": "#00ff00", "stretch": True})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.mediawall"
            save_project(self.scene, path)
            loaded, warnings = load_project(path)
        obj = loaded.get(self.text.id)
        self.assertEqual(warnings, [])
        self.assertEqual((obj.text, obj.text_style), (self.text.text, self.text.text_style))

    def test_load_repairs_a_damaged_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.mediawall"
            save_project(self.scene, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["objects"][0]["text_style"] = {"fill": 5, "depth": 400}
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded, _ = load_project(path)
        style = loaded.get(self.text.id).text_style
        self.assertEqual((style["fill"], style["depth"]), ("#ffffff", 40))


if __name__ == "__main__":
    unittest.main()
