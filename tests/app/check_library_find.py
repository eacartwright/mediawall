"""
The Library's Find mode and its ways to the wall (readme section 44.5):
filters as chips, excluding, finding by a parent tag, limiting to a folder,
narrowing by what's left, missing files, Add to Wall, and files dropped on
the wall. A real drag needs a real mouse, so what's tested here is what it
carries, and the wall's side, with drop events.
"""

import os
import shutil

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QGuiApplication, QKeyEvent
from PySide6.QtTest import QTest

from harness import AUDIO, GIF, MOV, OUT, PHOTO, Check, Qt, SCREENSHOT, media
from core.scene import Scene

c = Check("library_find")


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy(source, target)


FOLDER = OUT / "media"
link(media(PHOTO), FOLDER / "cars" / "red_car.jpg")
link(media(SCREENSHOT), FOLDER / "cars" / "blue_ferrari.png")
link(media(GIF), FOLDER / "cars" / "race.gif")
link(media(MOV), FOLDER / "boston.mov")
link(media(AUDIO), FOLDER / "boston_song.m4a")
GONE = FOLDER / "gone.jpg"
link(media(PHOTO), GONE)

scene = Scene()
box = scene.add_object("container", 700, 300, width=300, height=200)


def window():
    return c.js("libraryLoader.item")


def item(object_name, expression):
    return c.js("""(function() {
        function walk(item) {
            if (item.objectName === %r) return item
            for (var i = 0; i < item.children.length; i++) {
                var hit = walk(item.children[i]); if (hit) return hit
            }
            return null
        }
        var item = walk(libraryLoader.item.Overlay.overlay.parent)
        if (!item) return null
        return (%s)
    })()""" % (object_name, expression))


def key(which, modifiers=Qt.NoModifier):
    if not window().isActive():
        print(f"NOTE  the Library isn't the active window (key {which})", flush=True)
    QTest.keyClick(window(), which, modifiers)


def type_text(text):
    win = window()
    for letter in text:
        code = Qt.Key(ord(letter.upper()))
        QGuiApplication.sendEvent(win, QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, letter))
        QGuiApplication.sendEvent(win, QKeyEvent(QEvent.KeyRelease, code, Qt.NoModifier, letter))


def names():
    """The file list, as listed."""
    return sorted(c.js("""(function() {
        var files = tagLibrary.files, names = []
        for (var i = 0; i < files.rowCount(); i++) names.push(tagLibrary.fileAt(i).name)
        return names })()"""))


def chips():
    return c.js("tagLibrary.filters.map(function(f) { return (f.exclude ? '-' : '') + f.name })")


def tree_names():
    return item("libraryTagTree", """(function() {
        var rows = []
        for (var i = 0; i < item.count; i++) {
            var row = item.itemAtIndex(i)
            if (row) rows.push(row.name + ":" + row.count)
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


def tag(names_in_row, tag_name):
    """Select these files by name and tag them."""
    rows = c.js("""(function() {
        var files = tagLibrary.files, rows = []
        for (var i = 0; i < files.rowCount(); i++) rows.push(tagLibrary.fileAt(i).name)
        return rows })()""")
    first = True
    for i, name in enumerate(rows):
        if name in names_in_row:
            c.js("tagLibrary.clickFile(%d, %s, false)" % (i, "false" if first else "true"))
            first = False
    c.js("tagLibrary.createAndApply(%r)" % tag_name)


def label():
    return item("librarySelection", "item.text")


def step_open():
    c.js("showLibrary()")
    window().requestActivate()
    c.js("tagLibrary.subfolders = true")
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_tag_them():
    # car > ferrari, in a group that's only for tidiness; and some loose tags.
    tag(["blue_ferrari.png"], "ferrari")
    tag(["red_car.jpg", "race.gif"], "car")
    c.js("tagLibrary.createGroup('Things', -1)")
    tag(["red_car.jpg", "boston.mov"], "red")
    tag(["boston.mov", "boston_song.m4a", "gone.jpg"], "boston")
    c.js("tagLibrary.setQuery('ferrari')")
    ferrari = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('car')")
    car = c.js("tagLibrary.results[0].id")
    c.js("tagLibrary.setQuery('')")
    c.js("tagLibrary.moveTag(%d, %d)" % (ferrari, car))
    c.check("all files are listed in Tag mode", len(names()) == 6, str(names()))
    window().grabWindow().save(str(OUT / "library-tagged.png"))
    key(Qt.Key_Tab)


def step_find():
    c.check("Tab switches to Find", c.js("tagLibrary.findMode") is True)
    c.check("...and the box keeps the focus", item("librarySearch", "item.activeFocus") is True)
    c.check("Find looks clearly different", str(item("libraryChips", "item.parent.color")) != "#303030")
    c.check("with no filters: everything tagged, wherever it is",
            names() == ["blue_ferrari.png", "boston.mov", "boston_song.m4a", "gone.jpg", "race.gif", "red_car.jpg"],
            str(names()))
    c.check("the label counts what's found", label().startswith("Found 6 files"), label())
    type_text("car")
    c.check("the results come as you type", c.js("tagLibrary.results[0].name") == "car")
    key(Qt.Key_Return)


def step_chip():
    c.check("Enter adds it as a chip, and clears the box", chips() == ["car"] and item("librarySearch", "item.text") == "")
    c.check("a parent tag finds its children too",
            names() == ["blue_ferrari.png", "race.gif", "red_car.jpg"], str(names()))
    tree = tree_names()
    c.check("the pane shows only tags in these results", any(n.startswith("red:") for n in tree)
            and not any(n.startswith("boston:") for n in tree), str(tree))
    c.check("...with counts among them", "red:1" in tree and "car:3" in tree, str(tree))
    window().grabWindow().save(str(OUT / "library-find.png"))
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, tree_point("red"))


def step_narrowed():
    c.check("clicking a tag in the pane narrows the search", chips() == ["car", "red"], str(chips()))
    c.check("filters combine as AND", names() == ["red_car.jpg"], str(names()))
    key(Qt.Key_Backspace)


def step_exclude():
    c.check("Backspace in the empty box takes the last filter off", chips() == ["car"], str(chips()))
    type_text("-ferrari")
    c.check("a leading - offers to exclude", c.js("tagLibrary.results[0].exclude") is True)
    key(Qt.Key_Return)


def step_excluded():
    c.check("-tag excludes it", chips() == ["car", "-ferrari"], str(chips()))
    c.check("...and what it's on", names() == ["race.gif", "red_car.jpg"], str(names()))
    fid = c.js("tagLibrary.filters[1].id")
    c.js("tagLibrary.removeFilter(%d)" % fid)
    c.js("tagLibrary.removeFilter(tagLibrary.filters[0].id)")
    type_text("boston")
    key(Qt.Key_Return)


def step_missing():
    c.check("the search so far", names() == ["boston.mov", "boston_song.m4a", "gone.jpg"], str(names()))
    GONE.unlink()
    c.js("tagLibrary.removeFilter(tagLibrary.filters[0].id)")
    type_text("boston")
    key(Qt.Key_Return)


def step_missing_shown():
    rows = [c.js("tagLibrary.fileAt(%d).name" % i) for i in range(3)]
    row = rows.index("gone.jpg")
    c.check("a file that has gone is still found, as missing", c.js("tagLibrary.fileAt(%d).missing" % row) is True)
    c.check("its tile says so",
            item("libraryGrid", "item.itemAtIndex(%d).missing" % row) is True)
    c.check("...and it has no thumbnail", item("libraryGrid", "item.itemAtIndex(%d).thumb" % row) == "")
    window().grabWindow().save(str(OUT / "library-missing.png"))

    c.js("tagLibrary.selectAll()")
    key(Qt.Key_Return, Qt.ControlModifier)


def step_added():
    c.check("Ctrl+Enter: the video goes on the canvas, and the missing file doesn't",
            len(media_objects()) == 1 and c.scene.sources[media_objects()[0].source_id].path.endswith("boston.mov"),
            str(media_objects()))
    c.check("...and audio to the Playback tab", len(c.scene.audio_tracks()) == 1)
    c.check("...and it says what happened", "Added 2" in item("libraryMessage", "item.text")
            and "1 missing" in item("libraryMessage", "item.text"), item("libraryMessage", "item.text"))
    c.check("it's one undo step on the wall", c.js("sceneModel.canUndo") is True)
    c.js("sceneModel.undo()")
    c.check("...which takes it all back",
            media_objects() == [] and len(c.scene.audio_tracks()) == 0 and c.js("sceneModel.canUndo") is False)
    c.js("tagLibrary.selectAll()")
    item("libraryAddToWall", "item.clicked()")


def step_button():
    c.check("the Add to Wall button does the same", len(media_objects()) == 1)
    c.check("the wall is marked as changed", c.js("sceneModel.canUndo") is True)
    c.js("sceneModel.undo()")
    c.js("window.presenting = true")
    c.js("tagLibrary.selectAll()")
    item("libraryAddToWall", "item.clicked()")
    c.check("nothing goes on the wall during Present", media_objects() == [])
    c.check("...and it says so", "Present" in item("libraryMessage", "item.text"))
    c.js("window.presenting = false")


def step_drag_contents():
    urls = c.js("tagLibrary.dragUrls(0)")
    c.check("a drag carries the selection's files, as file URLs",
            urls.count("file://") == 2 and "\r\n" in urls, repr(urls[:60]))
    c.check("...not the missing file", "gone.jpg" not in urls)
    row = next(i for i in range(3) if c.js("tagLibrary.fileAt(%d).name" % i) == "boston.mov")
    c.js("tagLibrary.clickFile(%d, false, false)" % row)
    single = c.js("tagLibrary.dragUrls(%d)" % row)
    c.check("dragging one file carries it alone", single.count("file://") == 1 and single.endswith("boston.mov"), single)
    other = next(i for i in range(3) if c.js("tagLibrary.fileAt(%d).name" % i) == "boston_song.m4a")
    c.check("dragging a tile not selected selects it",
            c.js("tagLibrary.dragUrls(%d)" % other).endswith("boston_song.m4a") and c.js("tagLibrary.selectedCount") == 1)
    c.win.requestActivate()


def drop_on_wall(paths, x, y):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    point = QPoint(x, y)
    win = c.win
    actions = Qt.CopyAction
    QGuiApplication.sendEvent(win, QDragEnterEvent(point, actions, mime, Qt.LeftButton, Qt.NoModifier))
    QGuiApplication.sendEvent(win, QDragMoveEvent(point, actions, mime, Qt.LeftButton, Qt.NoModifier))
    event = QDropEvent(QPointF(point), actions, mime, Qt.LeftButton, Qt.NoModifier)
    QGuiApplication.sendEvent(win, event)
    return event


def media_objects():
    return [o for o in c.scene.objects if o.type == "media" and o.parent_id is None]


def step_drop_canvas():
    drop_on_wall([FOLDER / "boston.mov", FOLDER / "cars" / "red_car.jpg"], 300, 200)
    placed = sorted((round(o.x), round(o.y)) for o in media_objects())
    c.check("files dropped on the canvas are added, from where they were dropped",
            placed == [(300, 200), (330, 230)], str(placed))
    c.js("sceneModel.undo()")
    c.check("...as one undo step", media_objects() == [], str(media_objects()))
    c.js("sceneModel.select(%r)" % box.id)


def step_drop_container():
    # Box at (700, 300), 300 x 200.
    drop_on_wall([FOLDER / "cars" / "red_car.jpg"], 800, 400)
    content = c.scene.content_of(box.id)
    c.check("a file dropped on an empty container goes in it", content is not None and media_objects() == [],
            str(content))
    drop_on_wall([FOLDER / "boston_song.m4a"], 300, 200)
    c.check("dropped audio goes to the Playback tab", len(c.scene.audio_tracks()) == 1)
    before = len(media_objects())
    notes = OUT / "notes.txt"
    notes.write_text("not media", encoding="utf-8")
    drop_on_wall([notes], 300, 200)
    c.check("a file that isn't media is ignored", len(media_objects()) == before)
    c.js("window.presenting = true")


def step_drop_present():
    before = len(media_objects())
    drop_on_wall([FOLDER / "boston.mov"], 300, 200)
    c.check("nothing can be dropped during Present", len(media_objects()) == before)
    c.js("window.presenting = false")
    window().requestActivate()


def step_folder_limit():
    c.js("tagLibrary.removeFilter(tagLibrary.filters[0].id)")
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER / "cars"))


def step_folder_limited():
    c.check("clicking a folder limits the search to it",
            names() == ["blue_ferrari.png", "race.gif", "red_car.jpg"], str(names()))
    c.js("tagLibrary.setFolder('')")


def step_tag_mode():
    c.check("...until it's taken off", len(names()) == 6, str(names()))
    item("libraryTagButton", "item.clicked()")


def step_back_in_tag_mode():
    c.check("the Tag button goes back", c.js("tagLibrary.findMode") is False)
    c.check("...to the folder it was on", c.js("tagLibrary.folder") == FOLDER.as_posix(), c.js("tagLibrary.folder"))
    tree = tree_names()
    c.check("...with every tag", any(n.startswith("boston:") for n in tree) and any(n.startswith("ferrari:") for n in tree), str(tree))
    c.check("the search in Find is kept for going back", c.js("tagLibrary.filters.length") == 0)
    type_text("zzz")
    c.check("Tag mode offers to create again", c.js("tagLibrary.results[0].create") is True)
    key(Qt.Key_Escape)
    c.finish()


c.run(scene, [
    (800, step_open), (1500, step_tag_them), (1000, step_find), (500, step_chip), (500, step_narrowed),
    (500, step_exclude), (500, step_excluded), (500, step_missing), (500, step_missing_shown),
    (400, step_added), (400, step_button), (300, step_drag_contents), (500, step_drop_canvas),
    (300, step_drop_container), (300, step_drop_present), (300, step_folder_limit),
    (500, step_folder_limited), (500, step_tag_mode), (800, step_back_in_tag_mode),
])
