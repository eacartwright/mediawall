"""
The Library: deleting files, the grid's wheel, the tags pane's width, and
renaming a tag (the dialog's title, and undoing it).

Deleted files go to a scratch folder rather than the real Trash, unless
MEDIAWALL_CHECK_REAL_TRASH is set: this runs on every check, and each run
would leave its files there. With it set, they really go to the Trash.
"""

import os
import shutil

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from harness import OUT, Check, Qt, SCREENSHOT, VIDEO, media
import bridge.library_model as library_model
from core.scene import Scene

c = Check("library_edits")

FOLDER = OUT / "edits"
FOLDER.mkdir(parents=True, exist_ok=True)
NAMES = [f"pic{i:02}.png" for i in range(1, 25)]
for name in NAMES:
    shutil.copy(media(SCREENSHOT), FOLDER / name)
shutil.copy(media(VIDEO), FOLDER / "zz-video.mp4")

SCRATCH_TRASH = OUT / "scratch-trash"
SCRATCH_TRASH.mkdir(exist_ok=True)
refused = set()                      # names that "can't be moved"
real_move_to_trash = library_model.move_to_trash


def fake_move_to_trash(path):
    if os.path.basename(path) in refused:
        return False
    if os.environ.get("MEDIAWALL_CHECK_REAL_TRASH"):
        return real_move_to_trash(path)
    shutil.move(path, SCRATCH_TRASH / os.path.basename(path))
    return True


library_model.move_to_trash = fake_move_to_trash


def window():
    return c.js("libraryLoader.item")


def item(object_name, expression):
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


def grid(expression):
    return item("libraryGrid", expression)


def key(which, modifiers=Qt.NoModifier):
    QTest.keyClick(window(), which, modifiers)


def message():
    return item("libraryMessage", "item.text")


def row_of(name):
    for row in range(c.js("tagLibrary.fileCount")):
        if c.js("tagLibrary.fileAt(%d).name" % row) == name:
            return row
    return -1


def tile_point(row):
    grid("item.positionViewAtIndex(%d, GridView.Contain)" % row)
    found = grid("""(function() {
        var tile = item.itemAtIndex(%d)
        var p = tile.mapToItem(null, tile.width / 2, tile.height / 2)
        return [p.x, p.y] })()""" % row)
    return QPoint(round(found[0]), round(found[1]))


def trash_dialog_open():
    return c.js("libraryLoader.item.trashAsk.visible") is True


def on_disk(name):
    return (FOLDER / name).exists()


def tag_id(name):
    c.js("tagLibrary.setQuery(%r)" % name)
    found = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('')")
    return found


def tree_names():
    return item("libraryTagTree", """(function() {
        var rows = []
        for (var i = 0; i < item.count; i++) {
            var row = item.itemAtIndex(i)
            if (row) rows.push(row.name)
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


# ---- Opening ----

def step_open():
    c.key(Qt.Key_L, Qt.ControlModifier)


def step_opened():
    window().requestActivate()
    c.js("appSettings.libraryTileSize = 200")
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_scanned():
    c.check("the folder is listed", c.js("tagLibrary.fileCount") == len(NAMES) + 1,
            str(c.js("tagLibrary.fileCount")))
    width = item("libraryTagsPane", "item.width")
    c.check("the tags pane starts 230 wide", width == 230, str(width))


# ---- The wheel ----

def wheel_at_grid(delta):
    p = item("libraryGridWheel", """(function() {
        var p = item.mapToItem(null, item.width / 2, item.height / 2)
        return [p.x, p.y] })()""")
    c.wheel(p[0], p[1], delta, window=window())


def step_wheel():
    grid("item.positionViewAtBeginning()")
    start = grid("item.contentY")
    wheel_at_grid(-120)
    moved = grid("item.contentY") - start
    cell = grid("item.cellHeight")
    c.check("a notch down moves the grid a whole row", moved == cell, f"{moved} of {cell}")
    wheel_at_grid(120)
    c.check("a notch up comes back", grid("item.contentY") == start)
    wheel_at_grid(120)
    c.check("it stops at the top", grid("item.contentY") == start)
    wheel_at_grid(-120 * 100)
    furthest = grid("item.originY + item.contentHeight - item.height")
    c.check("it stops at the bottom", grid("item.contentY") == furthest,
            f'{grid("item.contentY")} of {furthest}')
    grid("item.positionViewAtBeginning()")


# ---- Deleting ----

def step_delete_key():
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, tile_point(row_of("pic03.png")))
    key(Qt.Key_Delete)
    c.check("Delete asks first", trash_dialog_open())
    question = c.js("libraryLoader.item.trashAsk.question")
    c.check("...naming the file, and saying its tags go",
            '"pic03.png"' in question and "tags" in question, question)
    window().grabWindow().save(str(OUT / "library-trash-dialog.png"))
    key(Qt.Key_Escape)


def step_cancelled():
    c.check("Esc cancels", not trash_dialog_open() and on_disk("pic03.png"))
    c.check("...and the box has the focus back", item("librarySearch", "item.activeFocus") is True)
    c.js("tagLibrary.createAndApply('doomed')")
    tag = tag_id("doomed")
    c.check("the file gets a tag, to see it go", c.js("tagLibrary.tagUsage(%d)" % tag) == 1)
    c.js("tagLibrary.stepFile(1)")
    c.js("tagLibrary.createAndApply('kept')")
    c.js("tagLibrary.stepFile(-1)")
    key(Qt.Key_Delete)
    key(Qt.Key_Return)


def step_deleted():
    c.check("Enter confirms, and the file leaves the disk", not on_disk("pic03.png"))
    c.check("...for the Trash", os.environ.get("MEDIAWALL_CHECK_REAL_TRASH") is not None
            or (SCRATCH_TRASH / "pic03.png").exists())
    c.check("...and from the list", row_of("pic03.png") == -1 and c.js("tagLibrary.fileCount") == len(NAMES))
    c.check("the next file is selected", c.js("tagLibrary.fileAt(tagLibrary.currentRow).name") == "pic04.png"
            and c.js("tagLibrary.selectedCount") == 1, str(c.js("tagLibrary.currentRow")))
    c.check("...and its tile shows it", grid("item.itemAtIndex(tagLibrary.currentRow).selected") is True)
    c.check("the tag's count goes down", c.js("tagLibrary.tagUsage(%d)" % tag_id("doomed")) == 0)
    c.check("other tiles keep their tags", grid("item.itemAtIndex(tagLibrary.currentRow).tagged") is True)
    c.check("the status bar says so", "Moved 1 file" in message(), message())
    c.check("the box has the focus back", item("librarySearch", "item.activeFocus") is True)
    c.js("tagLibrary.say('')")
    # Several files, one of which can't be moved.
    refused.add("pic06.png")
    c.js("tagLibrary.clickFile(%d, false, false)" % row_of("pic05.png"))
    c.js("tagLibrary.clickFile(%d, false, true)" % row_of("pic07.png"))
    key(Qt.Key_Delete)
    question = c.js("libraryLoader.item.trashAsk.question")
    c.check("several: it says how many", "3 files" in question and "Their tags" in question, question)
    key(Qt.Key_Return)


def step_some_refused():
    c.check("what can move, goes", not on_disk("pic05.png") and not on_disk("pic07.png"))
    c.check("what can't, stays: on disk, listed, and selected",
            on_disk("pic06.png") and row_of("pic06.png") >= 0
            and c.js("tagLibrary.selectedCount") == 1
            and c.js("tagLibrary.fileAt(tagLibrary.currentRow).name") == "pic06.png")
    c.check("...and it says so", "Moved 2 files" in message() and "1 file couldn't" in message(), message())
    refused.clear()
    # By mouse: a tile outside the selection is what the menu acts on.
    global scrolled_to
    spot = tile_point(row_of("pic20.png"))
    scrolled_to = grid("item.contentY")
    c.check("(the view is scrolled down, for what follows)", scrolled_to > 0, str(scrolled_to))
    QTest.mouseClick(window(), Qt.RightButton, Qt.NoModifier, spot)


def step_menu_open():
    c.check("right-click selects the tile", c.js("tagLibrary.fileAt(tagLibrary.currentRow).name") == "pic20.png")
    spot = item("libraryTrashItem", """(function() {
        var p = item.mapToItem(null, item.width / 2, item.height / 2)
        return [p.x, p.y] })()""")
    c.check("...and opens its menu", spot is not None)
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, QPoint(round(spot[0]), round(spot[1])))


def step_menu_chose():
    c.check("the menu asks first", trash_dialog_open())
    key(Qt.Key_Return)


def step_menu_deleted():
    c.check("the tile's menu deletes it", not on_disk("pic20.png"), message())
    c.check("the view stays where it was scrolled", grid("item.contentY") == scrolled_to,
            f'{grid("item.contentY")} from {scrolled_to}')
    # The last file, playing in Strip view.
    c.js("tagLibrary.clickFile(%d, false, false)" % row_of("zz-video.mp4"))
    c.js("libraryLoader.item.stripView = true")


def step_strip_playing():
    c.check("Strip opens the video", item("libraryStripView", "item.item !== null") is True)
    key(Qt.Key_Delete)
    c.check("Delete lets go of the file before asking",
            item("libraryStripView", "item.item === null") is True and trash_dialog_open())
    key(Qt.Key_Escape)


def step_strip_cancelled():
    c.check("Cancel opens the file again", item("libraryStripView", "item.item !== null") is True)
    key(Qt.Key_Delete)
    key(Qt.Key_Return)


def step_strip_deleted():
    c.check("a video that was playing can go", not on_disk("zz-video.mp4"), message())
    c.check("the last file gone: the one before it is selected",
            c.js("tagLibrary.fileAt(tagLibrary.currentRow).name") == "pic24.png"
            and c.js("tagLibrary.selectedCount") == 1)
    c.check("...and Strip shows it", item("libraryStripView", "item.item !== null") is True)
    c.js("libraryLoader.item.stripView = false")


# ---- Renaming ----

def step_rename_menu():
    c.js("tagLibrary.createAndApply('race-car')")
    QTest.mouseClick(window(), Qt.RightButton, Qt.NoModifier, tree_point("race-car"))


def step_rename_item():
    spot = item("libraryRenameItem", """(function() {
        var p = item.mapToItem(null, item.width / 2, item.height / 2)
        return [p.x, p.y] })()""")
    c.check("the tag's menu has Rename", spot is not None)
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, QPoint(round(spot[0]), round(spot[1])))


def step_rename_dialog():
    # A Dialog isn't an item, so this looks for its title as shown.
    title = c.js("""(function() {
        function walk(item) {
            if (item.text === "Rename race-car" && item.visible) return true
            for (var i = 0; i < item.children.length; i++)
                if (walk(item.children[i])) return true
            return false
        }
        return walk(libraryLoader.item.Overlay.overlay) })()""")
    c.check("the dialog's title names the tag", title is True)
    window().grabWindow().save(str(OUT / "library-rename.png"))
    c.check("the name is there to edit", item("libraryNameField", "item.text") == "race-car")
    item("libraryNameField", "item.text = 'race car'")
    key(Qt.Key_Return)


def step_renamed():
    c.check("it's renamed", "race car" in tree_names() and "race-car" not in tree_names(), str(tree_names()))
    c.check("Undo is there for it", c.js("tagLibrary.canUndo") is True)
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("Ctrl+Z puts the old name back", "race-car" in tree_names() and "race car" not in tree_names(),
            str(tree_names()))
    key(Qt.Key_Y, Qt.ControlModifier)
    c.check("Ctrl+Y renames it again", "race car" in tree_names() and "race-car" not in tree_names(),
            str(tree_names()))
    key(Qt.Key_Z, Qt.ControlModifier)
    # The old name taken since: undo refuses, and says why.
    c.js("tagLibrary.renameTag(%d, 'race car')" % tag_id("race-car"))
    c.js("tagLibrary.createGroup('Race-Car', -1)")
    key(Qt.Key_Z, Qt.ControlModifier)
    c.check("if the old name was taken since, undo says so", "already" in message(), message())
    c.check("...and changes nothing", "race car" in tree_names(), str(tree_names()))
    print(f"{sum(c.results)}/{len(c.results)} passed", flush=True)
    c.win.close()


c.run(Scene(), [
    (800, step_open), (800, step_opened), (1200, step_scanned), (300, step_wheel),
    (300, step_delete_key), (300, step_cancelled), (600, step_deleted), (600, step_some_refused),
    (300, step_menu_open), (300, step_menu_chose), (600, step_menu_deleted),
    (1000, step_strip_playing), (500, step_strip_cancelled), (1000, step_strip_deleted),
    (500, step_rename_menu), (300, step_rename_item), (300, step_rename_dialog), (300, step_renamed),
])
