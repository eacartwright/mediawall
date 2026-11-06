"""
The Library window (readme section 44): opening it, the folder scan, the
grid with its thumbnails and selection, the search box's keyboard flow,
the tags pane and editing the tree, and export/import. Everything runs on
a scratch database and thumbnail folder.
"""

import json
import os
import shutil
import sqlite3

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtTest import QTest

from harness import OUT, Check, GIF, PHOTO, Qt, SCREENSHOT, media
from core.scene import Scene

c = Check("library")

# A folder of its own, so the check isn't tied to what else is in tests/media.
FOLDER = OUT / "pictures"
(FOLDER / "deeper").mkdir(parents=True, exist_ok=True)
for i in range(1, 4):
    shutil.copy(media(SCREENSHOT), FOLDER / f"pic{i}.png")
shutil.copy(media(PHOTO), FOLDER / "photo.jpg")
shutil.copy(media(GIF), FOLDER / "deeper" / "moving.gif")
(FOLDER / "broken.jpg").write_bytes(b"not really a picture")
NAMES = ["broken.jpg", "photo.jpg", "pic1.png", "pic2.png", "pic3.png"]


def window():
    return c.js("libraryLoader.item")


def lib(expression):
    """A QML expression with `lib` = the Library window."""
    return c.js("(function() { var lib = libraryLoader.item; return (%s) })()" % expression)


def item(object_name, expression):
    """Like Check.item_js, within the Library window (and its dialogs)."""
    return c.js("""(function() {
        function walk(item) {
            if (item.objectName === %r && item.visible) return item
            for (var i = 0; i < item.children.length; i++) {
                var hit = walk(item.children[i]); if (hit) return hit
            }
            return null
        }
        var item = walk(libraryLoader.item.Overlay.overlay.parent)
        if (!item) return null
        return (%s)
    })()""" % (object_name, expression))


def click_item(object_name, button=Qt.LeftButton, at=None):
    spot = item(object_name, """(function() {
        var p = item.mapToItem(null, %s)
        return [p.x, p.y] })()""" % (at or "item.width / 2, item.height / 2"))
    QTest.mouseClick(window(), button, Qt.NoModifier, QPoint(round(spot[0]), round(spot[1])))


def key(which, modifiers=Qt.NoModifier):
    # A shortcut goes to the active window, whichever the key was sent to.
    if not window().isActive():
        print(f"NOTE  the Library isn't the active window (key {which})", flush=True)
    QTest.keyClick(window(), which, modifiers)


def type_text(text):
    # QTest.keyClicks takes only widgets.
    win = window()
    for letter in text:
        code = Qt.Key(ord(letter.upper()))
        QGuiApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, letter))
        QGuiApplication.sendEvent(win, QKeyEvent(QEvent.KeyRelease, code, Qt.NoModifier, letter))


def box_text():
    return item("librarySearch", "item.text")


def box_focused():
    return item("librarySearch", "item.activeFocus") is True


def selection_label():
    return item("librarySelection", "item.text")


def tile_point(row):
    """Where a tile is, in the window."""
    found = item("libraryGrid", """(function() {
        var tile = item.itemAtIndex(%d)
        var p = tile.mapToItem(null, tile.width / 2, tile.height / 2)
        return [p.x, p.y] })()""" % row)
    return QPoint(round(found[0]), round(found[1]))


def click_tile(row, modifiers=Qt.NoModifier):
    QTest.mouseClick(window(), Qt.LeftButton, modifiers, tile_point(row))


def tile(row, role):
    return item("libraryGrid", "item.itemAtIndex(%d).%s" % (row, role))


def tree_rows():
    return item("libraryTagTree", """(function() {
        var rows = []
        for (var i = 0; i < item.count; i++) {
            var row = item.itemAtIndex(i)
            if (row) rows.push([row.name, row.depth, row.count])
        }
        return rows })()""")


def tree_point(name):
    found = item("libraryTagTree", """(function() {
        for (var i = 0; i < item.count; i++) {
            var row = item.itemAtIndex(i)
            if (row && row.name === %r) {
                var p = row.mapToItem(null, row.width / 2, row.height / 2)
                return [p.x, p.y]
            }
        }
        return null })()""" % name)
    return QPoint(round(found[0]), round(found[1]))


def selection_tags():
    return c.js("tagLibrary.selectionTags")


def on_selection(name):
    return next((t for t in selection_tags() if t["name"] == name), None)


def database():
    return sqlite3.connect(os.environ["MEDIAWALL_LIBRARY"])


def links():
    with database() as db:
        rows = db.execute("""SELECT files.path, tags.name FROM file_tags
                             JOIN files ON files.id = file_id JOIN tags ON tags.id = tag_id""").fetchall()
    return sorted((os.path.basename(p), name) for p, name in rows)


def message():
    return item("libraryMessage", "item.text")


def step_closed():
    c.check("the Library isn't created until it's opened", c.js("libraryLoader.item === null") is True)
    c.check("...nor is the database", not os.path.exists(os.environ["MEDIAWALL_LIBRARY"]))
    last = c.center_of("toolbarPresent")
    c.check("the whole toolbar fits at the window's normal width (a smaller screen can't tell)",
            c.win.width() < 1280 or last[0] + last[2] / 2 <= c.win.width(), str(last))
    c.grab("toolbar.png")
    spot = c.center_of("toolbarLibrary")
    c.click(spot[0], spot[1])


def step_opened():
    win = window()
    c.check("the toolbar's button opens the Library", win is not None and win.isVisible())
    c.check("the database is made at the scratch path", os.path.exists(os.environ["MEDIAWALL_LIBRARY"]))
    c.check("the window can go behind the wall", lib("lib.transientParent === null") is True)
    win.requestActivate()
    c.check("nothing to show until a folder is chosen", c.js("tagLibrary.files.rowCount()") == 0)
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_scanned():
    c.check("the scan lists the folder's pictures (not subfolders)",
            c.js("tagLibrary.files.rowCount()") == len(NAMES), str(c.js("tagLibrary.files.rowCount()")))
    c.check("the first file starts selected", selection_label() == "Tagging 1 file", selection_label())
    c.check("the folder is remembered", c.js("appSettings.libraryFolder") == FOLDER.as_posix())
    c.check("the search box has the focus", box_focused())


def step_thumbnails():
    urls = [tile(i, "thumb") for i in range(len(NAMES))]
    c.check("a broken file has no thumbnail, and says so",
            urls[0] == "" and tile(0, "failed") is True, str(urls[0]))
    c.check("every other tile has a thumbnail from the scratch cache",
            all("thumbnails" in u and u.endswith(".jpg") for u in urls[1:]), str(urls[1:]))
    photo = urls[1].replace("file:///", "").replace("file://", "")
    if os.name != "nt":
        photo = "/" + photo
    from PySide6.QtGui import QImageReader
    size = QImageReader(photo).size()
    c.check("the thumbnail of a 4320 px photo is 320 px", max(size.width(), size.height()) == 320, str(size))
    c.check("the image in the tile has loaded",
            item("libraryGrid", "item.itemAtIndex(1).children[0].children[0].status === 1") is True)
    window().grabWindow().save(str(OUT / "library-grid.png"))


def step_selecting():
    click_tile(2)
    c.check("a click selects one file", selection_label() == "Tagging 1 file" and tile(2, "selected") is True)
    click_tile(4, Qt.ShiftModifier)
    c.check("Shift+click selects the range", selection_label() == "Tagging 3 files", selection_label())
    click_tile(3, Qt.ControlModifier)
    c.check("Ctrl+click takes one out", selection_label() == "Tagging 2 files", selection_label())
    c.check("the box keeps the focus through clicks", box_focused())


def step_create_first():
    click_tile(1)
    type_text("zebra")
    window().grabWindow().save(str(OUT / "library-create.png"))
    c.check("with no match, Enter offers to create it",
            c.js("tagLibrary.results[0].create") is True and c.js("tagLibrary.results[0].name") == "zebra")
    key(Qt.Key_Return)
    c.check("Enter makes the tag and applies it", links() == [("photo.jpg", "zebra")], str(links()))
    c.check("...and clears the box, keeping focus", box_text() == "" and box_focused())
    c.check("the tile shows it has tags", tile(1, "tagged") is True)
    c.check("the tags pane lists it as 1/1", on_selection("zebra")["count"] == 1)
    type_text("race car")
    key(Qt.Key_Return, Qt.ShiftModifier)
    c.check("Shift+Enter creates exactly what was typed", ("photo.jpg", "race car") in links(), str(links()))


def step_shift_enter_exact():
    type_text("race")
    c.check("typing part of a name finds it", c.js("tagLibrary.results[0].name") == "race car")
    key(Qt.Key_Return, Qt.ShiftModifier)
    c.check("Shift+Enter makes \"race\" instead of applying \"race car\"", ("photo.jpg", "race") in links(), str(links()))


def step_enter_top_result():
    click_tile(2)
    type_text("race")
    c.check("an exact name comes first", c.js("tagLibrary.results[0].name") == "race")
    c.check("the results show", item("libraryResults", "item.visible") is True)
    window().grabWindow().save(str(OUT / "library-results.png"))
    key(Qt.Key_Down)
    key(Qt.Key_Return)
    c.check("Down chooses the next result, and Enter applies it", ("pic1.png", "race car") in links(), str(links()))
    type_text("ZEB")
    key(Qt.Key_Return)
    c.check("Enter applies the top result, ignoring case", ("pic1.png", "zebra") in links(), str(links()))


def step_navigation():
    click_tile(1)
    key(Qt.Key_Right)
    c.check("Right in an empty box goes to the next file", tile(2, "current") is True)
    key(Qt.Key_Left)
    c.check("Left, the previous", tile(1, "current") is True)
    key(Qt.Key_Return)
    c.check("Enter in an empty box goes to the next file", tile(2, "current") is True)
    type_text("ab")
    key(Qt.Key_Left)
    c.check("with text, Left moves the cursor instead",
            tile(2, "current") is True and item("librarySearch", "item.cursorPosition") == 1)
    key(Qt.Key_Escape)
    c.check("Esc clears the box", box_text() == "")


def step_backspace_and_undo():
    click_tile(3)
    before = links()
    type_text("zebra")
    key(Qt.Key_Return)
    c.check("applied", ("pic2.png", "zebra") in links())
    key(Qt.Key_Backspace)
    c.check("Backspace in an empty box removes the last tag applied", links() == before, str(links()))
    type_text("zebra")
    key(Qt.Key_Return)
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("Ctrl+Z undoes it", links() == before, str(links()))
    key(Qt.Key_Y, Qt.ControlModifier)
    c.check("Ctrl+Y redoes it", ("pic2.png", "zebra") in links())
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("tagging doesn't touch the wall's undo", c.js("sceneModel.canUndo") is False)

    type_text("brand new")
    key(Qt.Key_Return, Qt.ShiftModifier)
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("undoing a created tag removes the tag too",
            all(row[0] != "brand new" for row in tree_rows()), str(tree_rows()))


def step_bulk():
    click_tile(2)
    click_tile(4, Qt.ShiftModifier)
    type_text("bulk")
    key(Qt.Key_Return)
    c.check("a tag goes on every selected file",
            [p for p, name in links() if name == "bulk"] == ["pic1.png", "pic2.png", "pic3.png"], str(links()))
    c.check("the selection stays after tagging", selection_label() == "Tagging 3 files")
    c.check("counts over the selection", on_selection("bulk")["count"] == 3 and on_selection("zebra")["count"] == 1)
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("a bulk action is one undo step",
            [p for p, name in links() if name == "bulk"] == [], str(links()))
    key(Qt.Key_Y, Qt.ControlModifier)


def step_pane_click():
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, tree_point("zebra"))
    c.check("clicking a tag not on all of them puts it on all",
            [p for p, name in links() if name == "zebra"].count("pic2.png") == 1, str(links()))
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, tree_point("zebra"))
    c.check("clicking it again takes it off them all",
            not any(name == "zebra" and p.startswith("pic") for p, name in links()), str(links()))
    c.check("the box has the focus back", box_focused())


def step_counts():
    rows = {row[0]: row[2] for row in tree_rows()}
    c.check("the tree shows each tag's file count, once tagging pauses",
            rows.get("bulk") == 3 and rows.get("zebra") == 1, str(rows))


def step_tree_group():
    c.check("a group is made through the pane", c.js("tagLibrary.createGroup('Location', -1)") is True)
    c.check("the name must be free", c.js("tagLibrary.createGroup('location', -1)") is False)
    c.check("...and the refusal is shown", "already" in message(), message())
    type_text("Locat")
    c.check("a group is never a result when tagging", c.js("tagLibrary.results[0].create") is True)
    key(Qt.Key_Escape)
    type_text("location")
    key(Qt.Key_Return, Qt.ShiftModifier)
    c.check("...and it can't be applied by typing its name",
            not any(name.lower() == "location" for _, name in links()) and "group" in message(), message())
    c.check("...the text stays, to correct", box_text() == "location")
    key(Qt.Key_Escape)


def step_drag_setup():
    click_tile(1)
    type_text("ferrari")
    key(Qt.Key_Return, Qt.ShiftModifier)
    type_text("sports")
    key(Qt.Key_Return, Qt.ShiftModifier)
    c.js("tagLibrary.removeLastApplied()")


def drag(start, end):
    win = window()
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
    for i in range(1, 7):
        QTest.mouseMove(win, QPoint(start.x() + (end.x() - start.x()) * i // 6,
                                    start.y() + (end.y() - start.y()) * i // 6))
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, end)


def step_drag():
    drag(tree_point("ferrari"), tree_point("sports"))


def step_dragged():
    names = [row[:2] for row in tree_rows()]
    c.check("dragging a tag onto another makes it a child", ["ferrari", 1] in names and
            names.index(["ferrari", 1]) == names.index(["sports", 0]) + 1, str(names))
    implied = on_selection("sports")
    c.check("the file now also counts as the parent, shown as from the child",
            implied is not None and implied["direct"] == 0 and implied["via"] == "ferrari", str(implied))
    c.check("the parent isn't stored on the file", ("photo.jpg", "sports") not in links())
    drag(tree_point("sports"), tree_point("Location"))


def step_dragged_to_group():
    names = [row[:2] for row in tree_rows()]
    c.check("a tag can be dragged into a group, with its children",
            ["sports", 1] in names and ["ferrari", 2] in names, str(names))
    drag(tree_point("Location"), tree_point("bulk"))


def step_refused_drag():
    names = [row[:2] for row in tree_rows()]
    c.check("a group can't go inside a tag", ["Location", 0] in names, str(names))
    c.check("...and it says why", "group" in message() and "bulk" in message(), message())
    window().grabWindow().save(str(OUT / "library-tree.png"))


def step_context_menu():
    QTest.mouseClick(window(), Qt.RightButton, Qt.NoModifier, tree_point("ferrari"))


def step_context_rename():
    # The menu's first items: New Group, Rename.
    menu = lib("""(function() {
        var pop = lib.Overlay.overlay.children
        for (var i = 0; i < pop.length; i++)
            if (pop[i].visible && pop[i].contentItem && pop[i].contentItem.count >= 5) return true
        return false })()""")
    c.check("right-click opens the tag's menu", menu is True)
    key(Qt.Key_Escape)
    c.check("Esc closes it, and the box has the focus back", box_focused())


def step_edit_dialogs():
    c.js("tagLibrary.setQuery('ferrari')")
    tag_id = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('')")
    c.check("rename", c.js("tagLibrary.renameTag(%d, 'Ferrari F40')" % tag_id) is True)
    c.check("...shows in the tree", any(row[0] == "Ferrari F40" for row in tree_rows()), str(tree_rows()))
    c.check("a tag used by files reports how many", c.js("tagLibrary.tagUsage(%d)" % tag_id) == 1)
    c.js("tagLibrary.setQuery('zebra')")
    zebra = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('')")
    c.check("merge", c.js("tagLibrary.mergeTag(%d, 'bulk')" % zebra) is True)
    c.check("...moves its files to the other tag",
            ("photo.jpg", "bulk") in links() and not any(n == "zebra" for _, n in links()), str(links()))
    c.check("merging into a name that doesn't exist is refused",
            c.js("tagLibrary.mergeTag(%d, 'nobody')" % tag_id) is False)
    c.js("tagLibrary.deleteTag(%d)" % tag_id)
    c.check("delete takes it off files", not any(n == "Ferrari F40" for _, n in links()), str(links()))


def step_filters():
    c.js("tagLibrary.subfolders = true")


def step_subfolders():
    c.check("Subfolders includes what's beneath", c.js("tagLibrary.files.rowCount()") == len(NAMES) + 1,
            str(c.js("tagLibrary.files.rowCount()")))
    c.js("tagLibrary.subfolders = false")
    c.js("tagLibrary.untaggedOnly = true")


def step_untagged():
    count = c.js("tagLibrary.files.rowCount()")
    tagged = {p for p, _ in links()}
    c.check("Untagged only leaves out what has tags", count == len(set(NAMES) - tagged), f"{count}, {tagged}")
    click_tile(0)
    # broken.jpg has no thumbnail, but can still be tagged.
    type_text("kept")
    key(Qt.Key_Return, Qt.ShiftModifier)
    c.check("a file just tagged stays in view until the next scan",
            c.js("tagLibrary.files.rowCount()") == count)
    c.js("tagLibrary.untaggedOnly = false")


def step_tile_size():
    before = item("libraryGrid", "item.cellWidth")
    c.js("appSettings.libraryTileSize = 100")
    c.check("the tile size setting changes the grid", item("libraryGrid", "item.cellWidth") < before)
    c.js("appSettings.libraryTileSize = 180")


def step_export_import():
    everything = OUT / "everything.json"
    tags_only = OUT / "tags-only.json"
    c.js("tagLibrary.exportTo(%r, true)" % str(everything))
    c.js("tagLibrary.exportTo(%r, false)" % str(tags_only))
    data = json.loads(everything.read_text(encoding="utf-8"))
    c.check("Export Everything holds tags and files",
            any(t["name"] == "bulk" for t in data["tags"]) and len(data["files"]) >= 3)
    c.check("Export Tags Only holds just the tags",
            "files" not in json.loads(tags_only.read_text(encoding="utf-8")))
    before = links()
    c.js("tagLibrary.importFrom(%r)" % str(everything))
    c.check("importing merges, changing nothing here", links() == before and "Imported 0 tags" in message(), message())
    c.js("tagLibrary.importFrom(%r)" % str(OUT / "no-such-file.json"))
    c.check("an unreadable import is refused with a message", "read" in message(), message())


def step_close():
    window().close()


def step_closed_again():
    c.check("closing destroys the window", c.js("libraryLoader.item === null") is True)
    c.key(Qt.Key_L, Qt.ControlModifier)


def step_reopened():
    c.check("Ctrl+L opens it again", window() is not None and window().isVisible())
    c.check("...as it was left",
            c.js("tagLibrary.folder") == FOLDER.as_posix() and c.js("tagLibrary.files.rowCount()") > 0)
    c.check("the folder tree opens to the folder", item("libraryFolderTree", """(function() {
        return item.rowAtIndex(tagLibrary.folderIndex(tagLibrary.folder)) })()""") >= 0)
    shown = item("libraryFolderTree", """(function() {
        var row = item.rowAtIndex(tagLibrary.folderIndex(tagLibrary.folder))
        var cell = item.itemAtCell(Qt.point(0, row))
        if (!cell) return null
        return [cell.highlighted, cell.contentItem.text, item.contentX] })()""")
    c.check("...highlighted, and not scrolled sideways, however deep it is",
            shown is not None and shown[0] is True and shown[1] == "pictures" and shown[2] == 0, str(shown))
    window().grabWindow().save(str(OUT / "library-reopened.png"))


def step_quit():
    # With the Library still open: the app must end, or run.py's time limit fails this.
    print(f"{sum(c.results)}/{len(c.results)} passed", flush=True)
    c.win.close()


c.run(Scene(), [
    (1000, step_closed), (800, step_opened), (1200, step_scanned), (3000, step_thumbnails),
    (100, step_selecting), (100, step_create_first), (500, step_shift_enter_exact),
    (100, step_enter_top_result), (100, step_navigation), (100, step_backspace_and_undo),
    (100, step_bulk), (100, step_pane_click), (600, step_counts), (100, step_tree_group),
    (100, step_drag_setup), (200, step_drag), (200, step_dragged), (200, step_dragged_to_group),
    (200, step_refused_drag), (100, step_context_menu), (200, step_context_rename),
    (100, step_edit_dialogs), (100, step_filters), (600, step_subfolders), (600, step_untagged),
    (600, step_tile_size), (100, step_export_import), (100, step_close), (400, step_closed_again),
    (800, step_reopened), (300, step_quit),
])
