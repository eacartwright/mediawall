import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.library import (
    FileSelection, Library, LibraryError, SCHEMA_VERSION, default_library_path,
    default_thumbnail_dir, file_fingerprint, found_entries, normalized_name, thumbnail_file,
)


class LibraryTestCase(unittest.TestCase):
    """A fresh in-memory library, and a temporary folder of real files."""

    def setUp(self):
        self.lib = Library()
        self.addCleanup(self.lib.close)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def file(self, name, data=b"data"):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data + name.encode())
        return str(path)

    def files(self, *names):
        return [self.file(n) for n in names]

    def found(self, *args, **kwargs):
        return [Path(row["path"]).name for row in self.lib.find(*args, **kwargs)]


class TreeRuleTests(LibraryTestCase):

    def test_names_are_unique_ignoring_case_across_tags_and_groups(self):
        self.lib.create_tag("Boston")
        with self.assertRaises(LibraryError):
            self.lib.create_tag("boston")
        with self.assertRaises(LibraryError):
            self.lib.create_group("BOSTON")

    def test_case_folding_beyond_ascii(self):
        self.lib.create_tag("Straße")
        with self.assertRaises(LibraryError):
            self.lib.create_tag("STRASSE")

    def test_name_clean_up_and_refusals(self):
        self.assertEqual(normalized_name("  race \t car "), "race car")
        for bad in ("", "   ", "-ferrari"):
            with self.assertRaises(LibraryError):
                normalized_name(bad)

    def test_rename_can_change_only_the_case(self):
        tag = self.lib.create_tag("boston")
        self.lib.rename(tag.id, "Boston")
        self.assertEqual(self.lib.tag(tag.id).name, "Boston")

    def test_rename_refuses_a_name_in_use(self):
        self.lib.create_tag("a")
        tag = self.lib.create_tag("b")
        with self.assertRaises(LibraryError):
            self.lib.rename(tag.id, "A")

    def test_group_cannot_go_inside_a_tag(self):
        car = self.lib.create_tag("car")
        group = self.lib.create_group("g")
        with self.assertRaises(LibraryError):
            self.lib.create_group("h", car.id)
        with self.assertRaises(LibraryError):
            self.lib.move(group.id, car.id)

    def test_tag_and_group_can_go_inside_a_group(self):
        group = self.lib.create_group("g")
        self.lib.create_group("h", group.id)
        self.lib.create_tag("t", group.id)
        self.assertEqual(len(self.lib.descendants(group.id)), 2)

    def test_move_refuses_loops(self):
        a = self.lib.create_tag("a")
        b = self.lib.create_tag("b", a.id)
        c = self.lib.create_tag("c", b.id)
        with self.assertRaises(LibraryError):
            self.lib.move(a.id, c.id)
        with self.assertRaises(LibraryError):
            self.lib.move(a.id, a.id)
        self.assertIsNone(self.lib.tag(a.id).parent_id)

    def test_tree_is_depth_first_with_siblings_by_name(self):
        loc = self.lib.create_group("Location")
        self.lib.create_tag("zebra")
        self.lib.create_tag("London", loc.id)
        ma = self.lib.create_tag("Massachusetts", loc.id)
        self.lib.create_tag("Boston", ma.id)
        self.assertEqual([(t.name, d) for t, d in self.lib.tree()], [
            ("Location", 0), ("London", 1), ("Massachusetts", 1), ("Boston", 2), ("zebra", 0)])

    def test_where_reads_from_the_top(self):
        loc = self.lib.create_group("Location")
        ma = self.lib.create_tag("Massachusetts", loc.id)
        boston = self.lib.create_tag("Boston", ma.id)
        self.assertEqual(self.lib.where(boston.id), "Location ▸ Massachusetts")
        self.assertEqual(self.lib.where(loc.id), "")
        self.assertTrue(self.lib.has_children(ma.id))
        self.assertFalse(self.lib.has_children(boston.id))

    def test_implied_stops_at_a_group(self):
        loc = self.lib.create_group("Location")
        ma = self.lib.create_tag("Massachusetts", loc.id)
        boston = self.lib.create_tag("Boston", ma.id)
        self.assertEqual([t.name for t in self.lib.implied(boston.id)], ["Massachusetts"])
        self.assertEqual([t.name for t in self.lib.ancestors(boston.id)], ["Massachusetts", "Location"])

    def test_delete_group_moves_contents_up(self):
        outer = self.lib.create_group("outer")
        inner = self.lib.create_group("inner", outer.id)
        tag = self.lib.create_tag("t", inner.id)
        self.lib.delete(inner.id)
        self.assertEqual(self.lib.tag(tag.id).parent_id, outer.id)
        self.assertIsNone(self.lib.tag(inner.id))

    def test_delete_tag_takes_it_off_files_and_keeps_its_children(self):
        path = self.file("a.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.apply_tag(car.id, [path])
        self.lib.delete(car.id)
        self.assertIsNone(self.lib.tag(ferrari.id).parent_id)
        self.assertEqual(self.lib.selection_tags([path]), [])

    def test_make_group_refused_while_used(self):
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [self.file("a.jpg")])
        with self.assertRaises(LibraryError):
            self.lib.make_group(tag.id)

    def test_make_group_refused_inside_a_tag(self):
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        with self.assertRaises(LibraryError):
            self.lib.make_group(ferrari.id)

    def test_make_group_then_it_no_longer_implies(self):
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.make_group(car.id)
        self.assertEqual(self.lib.implied(ferrari.id), [])

    def test_make_tag_refused_while_holding_groups(self):
        outer = self.lib.create_group("outer")
        self.lib.create_group("inner", outer.id)
        with self.assertRaises(LibraryError):
            self.lib.make_tag(outer.id)


class MergeTests(LibraryTestCase):

    def test_files_and_children_move_without_duplicates(self):
        both, one = self.files("both.jpg", "one.jpg")
        a = self.lib.create_tag("a")
        b = self.lib.create_tag("b")
        child = self.lib.create_tag("child", a.id)
        self.lib.apply_tag(a.id, [both, one])
        self.lib.apply_tag(b.id, [both])
        self.lib.merge(a.id, b.id)
        self.assertIsNone(self.lib.tag(a.id))
        self.assertEqual(self.lib.tag(child.id).parent_id, b.id)
        self.assertEqual(self.lib.tag(b.id).used, 2)

    def test_into_a_descendant_makes_no_loop(self):
        a = self.lib.create_tag("a")
        x = self.lib.create_tag("x", a.id)
        y = self.lib.create_tag("y", x.id)
        self.lib.merge(a.id, y.id)
        self.assertIsNone(self.lib.tag(y.id).parent_id)
        self.assertEqual(self.lib.tag(x.id).parent_id, y.id)
        self.assertEqual([t.name for t, _ in self.lib.tree()], ["y", "x"])

    def test_groups_refused(self):
        group = self.lib.create_group("g")
        tag = self.lib.create_tag("t")
        with self.assertRaises(LibraryError):
            self.lib.merge(tag.id, group.id)

    def test_forgets_undo_of_the_merged_tags(self):
        path = self.file("a.jpg")
        a = self.lib.create_tag("a")
        b = self.lib.create_tag("b")
        self.lib.apply_tag(a.id, [path])
        self.lib.merge(a.id, b.id)
        self.assertFalse(self.lib.can_undo())


class SearchTests(LibraryTestCase):

    def names(self, text, **kwargs):
        return [t.name for t in self.lib.search(text, **kwargs)]

    def test_ranking_by_how_it_matches(self):
        for name in ("scar", "big car", "car park", "car"):
            self.lib.create_tag(name)
        self.assertEqual(self.names("car"), ["car", "car park", "big car", "scar"])

    def test_ties_go_to_the_most_used(self):
        self.lib.create_tag("ant")
        self.lib.create_tag("axe")
        self.lib.apply_tag(self.lib.tag_by_name("axe").id, [self.file("a.jpg")])
        self.assertEqual(self.names("a"), ["axe", "ant"])

    def test_case_and_spaces_dont_matter(self):
        self.lib.create_tag("Race Car")
        self.assertEqual(self.names("  race   c"), ["Race Car"])

    def test_empty_text_has_no_results(self):
        self.lib.create_tag("a")
        self.assertEqual(self.names("  "), [])

    def test_groups_only_when_asked(self):
        self.lib.create_group("Location")
        self.assertEqual(self.names("loc"), [])
        self.assertEqual(self.names("loc", include_groups=True), ["Location"])

    def test_limit(self):
        self.lib.create_tag("a1")
        self.lib.create_tag("a2")
        self.assertEqual(self.names("a", limit=1), ["a1"])


class TaggingTests(LibraryTestCase):

    def test_first_tag_makes_a_file_row_with_a_fingerprint(self):
        path = self.file("a.jpg")
        self.assertEqual(self.lib.find(), [])
        self.lib.apply_tag(self.lib.create_tag("t").id, [path])
        row = self.lib._db.execute("SELECT path, media_type, fingerprint FROM files").fetchone()
        self.assertEqual(row, (path, "image", file_fingerprint(path)))

    def test_apply_counts_only_changes(self):
        a, b = self.files("a.jpg", "b.jpg")
        tag = self.lib.create_tag("t")
        self.assertEqual(self.lib.apply_tag(tag.id, [a]), 1)
        self.assertEqual(self.lib.apply_tag(tag.id, [a, b]), 1)
        self.assertEqual(self.lib.apply_tag(tag.id, [a, b]), 0)
        self.assertEqual(self.lib.tag(tag.id).used, 2)

    def test_group_cant_be_applied(self):
        group = self.lib.create_group("g")
        with self.assertRaises(LibraryError):
            self.lib.apply_tag(group.id, [self.file("a.jpg")])

    def test_files_that_cant_be_tagged_are_left_out(self):
        tag = self.lib.create_tag("t")
        changed = self.lib.apply_tag(tag.id, [
            str(self.dir / "gone.jpg"), self.file("notes.txt"), self.file("real.mp4")])
        self.assertEqual(changed, 1)

    def test_identical_copies_are_separate_files(self):
        a = self.dir / "a.jpg"
        b = self.dir / "b.jpg"
        a.write_bytes(b"same")
        b.write_bytes(b"same")
        self.lib.apply_tag(self.lib.create_tag("t").id, [str(a)])
        self.assertEqual(self.lib.untagged([str(a), str(b)]), [str(b)])

    @unittest.skipUnless(os.name == "nt", "Windows paths only")
    def test_windows_path_case_is_the_same_file(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [path])
        self.assertEqual(self.lib.apply_tag(tag.id, [path.upper()]), 0)

    def test_selection_counts_and_implied(self):
        a, b, c = self.files("a.jpg", "b.jpg", "c.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.apply_tag(ferrari.id, [a, b])
        self.lib.apply_tag(car.id, [b, c])
        rows = {r["tag"].name: r for r in self.lib.selection_tags([a, b, c])}
        self.assertEqual((rows["car"]["count"], rows["car"]["direct"], rows["car"]["via"]), (3, 2, ["ferrari"]))
        self.assertEqual((rows["ferrari"]["count"], rows["ferrari"]["direct"], rows["ferrari"]["via"]), (2, 2, []))

    def test_removing_leaves_a_direct_parent(self):
        path = self.file("a.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.apply_tag(ferrari.id, [path])
        self.lib.apply_tag(car.id, [path])
        self.lib.remove_tag(ferrari.id, [path])
        self.assertEqual([r["tag"].name for r in self.lib.selection_tags([path])], ["car"])

    def test_removing_the_child_removes_the_implied_tag(self):
        path = self.file("a.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.apply_tag(ferrari.id, [path])
        self.assertEqual(self.lib.remove_tag(car.id, [path]), 0)   # only implied: nothing to remove
        self.lib.remove_tag(ferrari.id, [path])
        self.assertEqual(self.lib.selection_tags([path]), [])

    def test_moving_a_tag_updates_files_at_once(self):
        path = self.file("a.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari")
        self.lib.apply_tag(ferrari.id, [path])
        self.assertEqual(self.found([car.id]), [])
        self.lib.move(ferrari.id, car.id)
        self.assertEqual(self.found([car.id]), ["a.jpg"])
        self.assertEqual(self.lib.tag_counts()[car.id], 1)

    def test_untagged_is_any_path_without_tags(self):
        a, b = self.files("a.jpg", "b.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [a, b])
        self.lib.remove_tag(tag.id, [b])     # its row stays; it's untagged again
        self.assertEqual(self.lib.untagged([a, b]), [b])

    def test_large_selection_spans_statement_chunks(self):
        paths = self.files(*[f"{i}.jpg" for i in range(7)])
        tag = self.lib.create_tag("t")
        with mock.patch("core.library._CHUNK", 3):
            self.assertEqual(self.lib.apply_tag(tag.id, paths), 7)
            self.assertEqual(self.lib.selection_tags(paths)[0]["count"], 7)
            self.assertEqual(self.lib.remove_tag(tag.id, paths), 7)
            self.assertEqual(len(self.lib.untagged(paths)), 7)


class FileSelectionTests(unittest.TestCase):

    def test_a_new_list_selects_its_first_row(self):
        selection = FileSelection(3)
        self.assertEqual((selection.selected, selection.current), ({0}, 0))
        selection.reset(0)
        self.assertEqual((selection.selected, selection.current), (set(), -1))

    def test_click_replaces(self):
        selection = FileSelection(5)
        selection.click(3)
        self.assertEqual((selection.selected, selection.current), ({3}, 3))

    def test_ctrl_click_toggles(self):
        selection = FileSelection(5)
        selection.click(2, ctrl=True)
        self.assertEqual(selection.selected, {0, 2})
        selection.click(0, ctrl=True)
        self.assertEqual(selection.selected, {2})

    def test_shift_click_spans_from_the_anchor_either_way(self):
        selection = FileSelection(9)
        selection.click(4)
        selection.click(6, shift=True)
        self.assertEqual(selection.selected, {4, 5, 6})
        selection.click(2, shift=True)
        self.assertEqual(selection.selected, {2, 3, 4})
        self.assertEqual(selection.current, 2)

    def test_ctrl_shift_click_adds_the_span(self):
        selection = FileSelection(9)
        selection.click(1)
        selection.click(4, ctrl=True)
        selection.click(6, ctrl=True, shift=True)
        self.assertEqual(selection.selected, {1, 4, 5, 6})

    def test_step_selects_only_the_next_and_stops_at_the_ends(self):
        selection = FileSelection(2)
        selection.select_all()
        self.assertTrue(selection.step(1))
        self.assertEqual(selection.selected, {1})
        self.assertFalse(selection.step(1))
        self.assertEqual(selection.selected, {1})

    def test_row_out_of_range_is_ignored(self):
        selection = FileSelection(2)
        selection.click(5)
        self.assertEqual(selection.selected, {0})

    def test_restore_keeps_rows_still_there(self):
        selection = FileSelection(9)
        selection.restore(3, {1, 2, 7}, 7)
        self.assertEqual((selection.selected, selection.current), ({1, 2}, 1))
        selection.restore(3, {8}, 8)
        self.assertEqual((selection.selected, selection.current), ({0}, 0))


class CountTests(LibraryTestCase):

    def test_a_file_counts_once_under_a_parent(self):
        path = self.file("a.jpg")
        car = self.lib.create_tag("car")
        ferrari = self.lib.create_tag("ferrari", car.id)
        self.lib.apply_tag(car.id, [path])
        self.lib.apply_tag(ferrari.id, [path])
        self.assertEqual(self.lib.tag_counts(), {car.id: 1, ferrari.id: 1})

    def test_limited_to_some_files(self):
        a, b = self.files("a.jpg", "b.jpg")
        car = self.lib.create_tag("car")
        red = self.lib.create_tag("red")
        self.lib.apply_tag(car.id, [a, b])
        self.lib.apply_tag(red.id, [a])
        ids = [row["id"] for row in self.lib.find([red.id])]
        self.assertEqual(self.lib.tag_counts(ids), {car.id: 1, red.id: 1})

    def test_group_has_no_count(self):
        group = self.lib.create_group("g")
        tag = self.lib.create_tag("t", group.id)
        self.lib.apply_tag(tag.id, [self.file("a.jpg")])
        self.assertNotIn(group.id, self.lib.tag_counts())


class FindTests(LibraryTestCase):

    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = self.files("a.jpg", "sub/b.jpg", "sub/deep/c.mp4")
        self.car = self.lib.create_tag("car")
        self.ferrari = self.lib.create_tag("ferrari", self.car.id)
        self.red = self.lib.create_tag("red")
        self.lib.apply_tag(self.ferrari.id, [self.a, self.b])
        self.lib.apply_tag(self.car.id, [self.c])
        self.lib.apply_tag(self.red.id, [self.a, self.c])

    def test_nothing_included_is_every_tagged_file(self):
        self.assertEqual(sorted(self.found()), ["a.jpg", "b.jpg", "c.mp4"])

    def test_a_parent_finds_its_children(self):
        self.assertEqual(sorted(self.found([self.car.id])), ["a.jpg", "b.jpg", "c.mp4"])
        self.assertEqual(sorted(self.found([self.ferrari.id])), ["a.jpg", "b.jpg"])

    def test_filters_combine_as_and(self):
        self.assertEqual(self.found([self.ferrari.id, self.red.id]), ["a.jpg"])

    def test_exclude(self):
        self.assertEqual(self.found([self.car.id], [self.ferrari.id]), ["c.mp4"])
        self.assertEqual(sorted(self.found([], [self.red.id])), ["b.jpg"])

    def test_finding_a_group_finds_what_it_holds(self):
        group = self.lib.create_group("Makes")
        self.lib.move(self.car.id, group.id)
        self.assertEqual(sorted(self.found([group.id])), ["a.jpg", "b.jpg", "c.mp4"])

    def test_empty_group_finds_nothing(self):
        self.assertEqual(self.found([self.lib.create_group("g").id]), [])

    def test_folder(self):
        sub = self.dir / "sub"
        self.assertEqual(sorted(self.found(folder=sub)), ["b.jpg", "c.mp4"])
        self.assertEqual(self.found(folder=sub, recursive=False), ["b.jpg"])
        self.assertEqual(self.found(folder=self.dir / "su"), [])     # a name's start isn't a folder

    def test_untagged_rows_arent_found(self):
        self.lib.remove_tag(self.red.id, [self.a, self.c])
        self.assertEqual(self.found([self.red.id]), [])
        self.lib.remove_tag(self.ferrari.id, [self.b])
        self.assertNotIn("b.jpg", self.found())

    def test_found_entries_look_like_a_folder_scan(self):
        entries = found_entries(self.lib.find([self.red.id]))
        by_name = {e["name"]: e for e in entries}
        self.assertEqual(set(by_name), {"a.jpg", "c.mp4"})
        self.assertFalse(by_name["a.jpg"]["missing"])
        self.assertEqual(by_name["a.jpg"]["url"], Path(self.a).as_uri())
        self.assertEqual(by_name["c.mp4"]["type"], "video")
        self.assertEqual(by_name["a.jpg"]["size"], os.path.getsize(self.a))

    def test_found_entries_mark_what_has_gone(self):
        os.unlink(self.a)
        entry = next(e for e in found_entries(self.lib.find()) if e["name"] == "a.jpg")
        self.assertTrue(entry["missing"])
        self.assertEqual(entry["url"], "")
        self.assertEqual(entry["path"], self.a)

    def test_found_entries_tell_gif_from_other_pictures(self):
        rows = [{"id": 1, "path": str(self.dir / "x.gif"), "type": "image", "size": 0, "mtime": 0.0}]
        self.assertTrue(found_entries(rows)[0]["animatable"])

    def test_row_contents(self):
        row = next(r for r in self.lib.find() if r["path"] == self.c)
        self.assertEqual(row["type"], "video")
        self.assertEqual(row["size"], os.path.getsize(self.c))


class UndoTests(LibraryTestCase):

    def test_bulk_apply_is_one_step(self):
        paths = self.files("a.jpg", "b.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, paths)
        self.assertTrue(self.lib.undo())
        self.assertFalse(self.lib.can_undo())
        self.assertEqual(self.lib.untagged(paths), paths)
        self.assertEqual(self.lib.tag(tag.id).used, 0)
        self.assertTrue(self.lib.redo())
        self.assertEqual(self.lib.untagged(paths), [])
        self.assertEqual(self.lib.tag(tag.id).used, 2)

    def test_undo_leaves_files_already_tagged(self):
        a, b = self.files("a.jpg", "b.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [a])
        self.lib.apply_tag(tag.id, [a, b])
        self.lib.undo()
        self.assertEqual(self.lib.untagged([a, b]), [b])

    def test_undo_remove_puts_links_back(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [path])
        self.lib.remove_tag(tag.id, [path])
        self.lib.undo()
        self.assertEqual(self.lib.untagged([path]), [])
        self.assertEqual(self.lib.tag(tag.id).used, 1)

    def test_no_change_isnt_a_step(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [path])
        self.lib.undo()
        self.lib.remove_tag(tag.id, [path])     # nothing to remove: redo survives
        self.assertTrue(self.lib.can_redo())
        self.assertEqual(self.lib.can_undo(), False)

    def test_new_action_clears_redo(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [path])
        self.lib.undo()
        self.lib.apply_tag(self.lib.create_tag("u").id, [path])
        self.assertFalse(self.lib.can_redo())

    def test_create_and_apply_undoes_the_new_tag_too(self):
        path = self.file("a.jpg")
        tag = self.lib.create_and_apply("  fresh tag ", [path])
        self.assertEqual(tag.name, "fresh tag")
        self.assertEqual(tag.used, 1)
        self.lib.undo()
        self.assertIsNone(self.lib.tag_by_name("fresh tag"))
        self.lib.redo()
        again = self.lib.tag_by_name("fresh tag")
        self.assertEqual(again.id, tag.id)
        self.assertEqual(self.lib.untagged([path]), [])

    def test_create_and_apply_keeps_a_tag_that_came_into_use(self):
        path = self.file("a.jpg")
        tag = self.lib.create_and_apply("x", [path])
        child = self.lib.create_tag("child", tag.id)
        self.lib.undo()
        self.assertIsNotNone(self.lib.tag(tag.id))
        self.assertEqual(self.lib.tag(child.id).parent_id, tag.id)

    def test_create_and_apply_with_an_existing_name_applies_it(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("Boston")
        self.assertEqual(self.lib.create_and_apply("boston", [path]).id, tag.id)
        self.lib.undo()
        self.assertIsNotNone(self.lib.tag(tag.id))

    def test_create_and_apply_refuses_a_groups_name(self):
        self.lib.create_group("Location")
        with self.assertRaises(LibraryError):
            self.lib.create_and_apply("location", [self.file("a.jpg")])

    def test_deleting_a_tag_forgets_only_its_steps(self):
        path = self.file("a.jpg")
        a = self.lib.create_tag("a")
        b = self.lib.create_tag("b")
        self.lib.apply_tag(a.id, [path])
        self.lib.apply_tag(b.id, [path])
        self.lib.delete(b.id)
        self.assertTrue(self.lib.undo())
        self.assertFalse(self.lib.can_undo())
        self.assertEqual(self.lib.untagged([path]), [path])

    def test_tree_edit_clears_redo_but_not_undo(self):
        path = self.file("a.jpg")
        a = self.lib.create_tag("a")
        self.lib.apply_tag(a.id, [path])
        self.lib.apply_tag(a.id, [self.file("b.jpg")])
        self.lib.undo()
        self.lib.rename(a.id, "renamed")
        self.assertFalse(self.lib.can_redo())
        self.assertTrue(self.lib.can_undo())

    def test_making_a_group_forgets_its_steps(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        self.lib.apply_tag(tag.id, [path])
        self.lib.remove_tag(tag.id, [path])
        self.lib.make_group(tag.id)
        self.assertFalse(self.lib.undo())       # would put a group on a file
        self.assertEqual(self.lib.untagged([path]), [path])

    def test_failed_transaction_changes_nothing(self):
        path = self.file("a.jpg")
        tag = self.lib.create_tag("t")
        with mock.patch("core.library.time.time", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.lib.apply_tag(tag.id, [path])
        self.assertEqual(self.lib.tag(tag.id).used, 0)
        self.assertEqual(self.lib._db.execute("SELECT COUNT(*) FROM files").fetchone()[0], 0)
        self.assertFalse(self.lib.can_undo())


class StorageTests(LibraryTestCase):

    def test_survives_reopening(self):
        db = self.dir / "made" / "here" / "library.sqlite"
        path = self.file("a.jpg")
        lib = Library(db)
        group = lib.create_group("Location")
        tag = lib.create_tag("Boston", group.id)
        lib.apply_tag(tag.id, [path])
        lib.close()

        lib = Library(db)
        self.addCleanup(lib.close)
        self.assertEqual([(t.name, d) for t, d in lib.tree()], [("Location", 0), ("Boston", 1)])
        self.assertEqual(lib.tag_by_name("boston").used, 1)
        self.assertEqual(lib.untagged([path]), [])
        self.assertFalse(lib.can_undo())         # undo lasts for the session

    def test_newer_database_is_refused(self):
        db = self.dir / "library.sqlite"
        Library(db).close()
        raw = sqlite3.connect(db)
        raw.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        raw.close()
        with self.assertRaises(LibraryError):
            Library(db)

    def test_a_file_that_isnt_a_database_is_refused(self):
        db = self.dir / "library.sqlite"
        db.write_bytes(b"this is not a database, at any length" * 100)
        with self.assertRaises(LibraryError):
            Library(db)

    def test_default_path_override(self):
        with mock.patch.dict(os.environ, {"MEDIAWALL_LIBRARY": "/somewhere/x.sqlite"}):
            self.assertEqual(default_library_path(), Path("/somewhere/x.sqlite"))

    @unittest.skipIf(os.name == "nt", "Linux paths only")
    def test_default_path_on_linux(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg"}):
            os.environ.pop("MEDIAWALL_LIBRARY", None)
            self.assertEqual(default_library_path(), Path("/xdg/Mediawall/library.sqlite"))

    @unittest.skipUnless(os.name == "nt", "Windows paths only")
    def test_default_path_on_windows(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:/Local"}):
            os.environ.pop("MEDIAWALL_LIBRARY", None)
            self.assertEqual(default_library_path(), Path("C:/Local/Mediawall/library.sqlite"))

    def test_thumbnail_dir_override(self):
        with mock.patch.dict(os.environ, {"MEDIAWALL_THUMBNAILS": "/somewhere/thumbs"}):
            self.assertEqual(default_thumbnail_dir(), Path("/somewhere/thumbs"))

    def test_thumbnail_file_changes_with_the_file(self):
        here = thumbnail_file("/cache", "/m/a.jpg", 10, 1.5)
        self.assertEqual(here, thumbnail_file("/cache", "/m/a.jpg", 10, 1.5))
        self.assertEqual(here.parent.parent, Path("/cache"))
        self.assertEqual(here.suffix, ".jpg")
        for other in [("/m/b.jpg", 10, 1.5), ("/m/a.jpg", 11, 1.5), ("/m/a.jpg", 10, 2.5)]:
            self.assertNotEqual(here, thumbnail_file("/cache", *other))

    def test_fingerprint(self):
        big = self.dir / "big.mp4"
        big.write_bytes(b"x" * 500_000)
        same = self.dir / "same.mp4"
        same.write_bytes(b"x" * 500_000)
        end_differs = self.dir / "end.mp4"
        end_differs.write_bytes(b"x" * 499_999 + b"y")
        self.assertEqual(file_fingerprint(big), file_fingerprint(same))
        self.assertNotEqual(file_fingerprint(big), file_fingerprint(end_differs))
        self.assertIsNone(file_fingerprint(self.dir / "gone.mp4"))


class ExportImportTests(LibraryTestCase):

    def setUp(self):
        super().setUp()
        self.path = self.file("a.jpg")
        location = self.lib.create_group("Location")
        ma = self.lib.create_tag("Massachusetts", location.id)
        self.boston = self.lib.create_tag("Boston", ma.id)
        self.lib.apply_tag(self.boston.id, [self.path])
        self.lib.create_tag("unused")
        self.export = self.dir / "export.json"

    def fresh(self):
        lib = Library()
        self.addCleanup(lib.close)
        return lib

    def test_round_trip_everything(self):
        self.lib.export_json(self.export)
        other = self.fresh()
        report = other.import_json(self.export)
        self.assertEqual((report["tags"], report["files"], report["links"], report["warnings"]), (4, 1, 1, []))
        self.assertEqual([(t.name, t.is_group, d) for t, d in other.tree()],
                         [(t.name, t.is_group, d) for t, d in self.lib.tree()])
        self.assertEqual(other.untagged([self.path]), [])
        self.assertEqual(other.tag_by_name("Boston").used, 1)

    def test_tags_only_holds_just_the_tree(self):
        self.lib.export_json(self.export, include_files=False)
        self.assertNotIn("files", json.loads(self.export.read_text(encoding="utf-8")))
        other = self.fresh()
        self.assertEqual(other.import_json(self.export)["tags"], 4)
        self.assertEqual(other.tag_by_name("Boston").used, 0)

    def test_untagged_files_arent_exported(self):
        self.lib.remove_tag(self.boston.id, [self.path])
        self.lib.export_json(self.export)
        self.assertEqual(json.loads(self.export.read_text(encoding="utf-8"))["files"], [])

    def test_import_merges_and_never_deletes(self):
        self.lib.export_json(self.export)
        other = self.fresh()
        mine = other.create_tag("Mine")
        moved = other.create_tag("boston", mine.id)     # same name, already placed here
        report = other.import_json(self.export)
        self.assertEqual(report["tags"], 3)
        self.assertEqual(other.tag(moved.id).parent_id, mine.id)
        self.assertEqual(other.tag(moved.id).name, "boston")
        self.assertEqual(other.tag(moved.id).used, 1)

    def test_importing_twice_adds_nothing(self):
        self.lib.export_json(self.export)
        report = self.lib.import_json(self.export)
        self.assertEqual((report["tags"], report["files"], report["links"]), (0, 0, 0))

    def test_a_path_not_here_stays_as_a_missing_file_with_its_fingerprint(self):
        gone = str(self.dir / "gone" / "x.mp4")
        self.export.write_text(json.dumps({
            "format": "mediawall-library", "version": 1,
            "tags": [{"name": "t"}],
            "files": [{"path": gone, "size": 5, "mtime": 1.5, "fingerprint": "5:abc", "tags": ["t"]}],
        }), encoding="utf-8")
        self.lib.import_json(self.export)
        self.assertIn(gone, [r["path"] for r in self.lib.find([self.lib.tag_by_name("t").id])])
        row = self.lib._db.execute("SELECT size, mtime, fingerprint FROM files WHERE path = ?", (gone,)).fetchone()
        self.assertEqual(row, (5, 1.5, "5:abc"))

    def test_parents_may_come_after_children(self):
        self.export.write_text(json.dumps({
            "format": "mediawall-library", "version": 1,
            "tags": [{"name": "child", "parent": "top"}, {"name": "top"}],
        }), encoding="utf-8")
        other = self.fresh()
        other.import_json(self.export)
        self.assertEqual(other.tag_by_name("child").parent_id, other.tag_by_name("top").id)

    def test_bad_entries_become_warnings(self):
        self.export.write_text(json.dumps({
            "format": "mediawall-library", "version": 1,
            "tags": ["nonsense", {"name": ""}, {"name": "-x"}, {"name": "ok"},
                     {"name": "loop1", "parent": "loop2"}, {"name": "loop2", "parent": "loop1"},
                     {"name": "orphan", "parent": "nobody"},
                     {"name": "G", "parent": "ok", "is_group": True}],
            "files": [7, {"path": 3}, {"path": "x.txt"},
                      {"path": str(self.dir / "y.jpg"), "size": "big", "tags": ["nobody", 5, "G"]}],
        }), encoding="utf-8")
        other = self.fresh()
        report = other.import_json(self.export)
        names = {t.name for t, _ in other.tree()}
        self.assertEqual(names, {"ok", "loop1", "loop2", "orphan", "G"})
        self.assertIsNone(other.tag_by_name("orphan").parent_id)
        self.assertIsNone(other.tag_by_name("G").parent_id)     # a group can't sit in a tag
        self.assertGreaterEqual(len(report["warnings"]), 9)
        self.assertEqual(report["links"], 0)

    def test_unusable_files_are_refused(self):
        for text in ("{not json", '{"format": "something-else"}', "[]",
                     '{"format": "mediawall-library", "version": 99}'):
            self.export.write_text(text, encoding="utf-8")
            with self.assertRaises(LibraryError):
                self.lib.import_json(self.export)
        with self.assertRaises(LibraryError):
            self.lib.import_json(self.dir / "no-such-file.json")

    def test_redo_doesnt_survive_an_import(self):
        self.lib.apply_tag(self.lib.tag_by_name("unused").id, [self.path])
        self.lib.undo()
        self.lib.export_json(self.export)
        self.lib.import_json(self.export)
        self.assertFalse(self.lib.can_redo())


if __name__ == "__main__":
    unittest.main()
