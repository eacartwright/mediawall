"""
The Library's folder tree (readme section 44.1) by mouse: the arrow opens and
closes a folder without choosing it, a click on the name chooses it, and a
double-click on the name also opens or closes it. The search box keeps the focus.
"""

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from harness import OUT, Check, Qt
from core.scene import Scene

c = Check("library_folders")

DEEP = OUT / "one" / "two" / "three" / "four" / "five" / "six" / "seven" / "eight" / "nine" / "ten"
DEEP.mkdir(parents=True, exist_ok=True)


def window():
    return c.js("libraryLoader.item")


def tree(expression):
    return c.js("""(function() {
        function walk(item) {
            if (item.objectName === "libraryFolderTree") return item
            for (var i = 0; i < item.children.length; i++) {
                var hit = walk(item.children[i]); if (hit) return hit
            }
            return null
        }
        var tree = walk(libraryLoader.item.Overlay.overlay.parent)
        var cell = function(row) { return tree.itemAtCell(Qt.point(0, row)) }
        return (%s)
    })()""" % expression)


def expanded(row=0):
    return tree("tree.isExpanded(%d)" % row)


def rows():
    return tree("tree.rows")


def arrow_point(row=0):
    """The middle of the arrow: everything left of the name."""
    found = tree("""(function() {
        var d = cell(%d)
        var p = d.mapToItem(null, d.leftMargin / 2, d.height / 2)
        return [p.x, p.y] })()""" % row)
    return QPoint(round(found[0]), round(found[1]))


def name_point(row=0):
    found = tree("""(function() {
        var d = cell(%d)
        var p = d.mapToItem(null, d.leftMargin + 8, d.height / 2)
        return [p.x, p.y] })()""" % row)
    return QPoint(round(found[0]), round(found[1]))


def click(where):
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, where)


def step_open():
    c.js("showLibrary()")
    window().requestActivate()


def step_arrow():
    c.check("the tree lists something", rows() >= 1, str(rows()))
    c.check("...closed to begin with", expanded() is False)
    c.closed_rows = rows()
    click(arrow_point())


def step_arrow_opened():
    c.check("a click on the arrow opens the folder", expanded() is True, str(rows()))
    c.check("...showing what's inside", rows() > c.closed_rows, f"{c.closed_rows} -> {rows()}")
    c.check("...without choosing it", c.js("tagLibrary.folder") == "", str(c.js("tagLibrary.folder")))
    c.check("...and the box keeps the focus", c.js("""(function() {
        return libraryLoader.item.activeFocusItem !== null
            && libraryLoader.item.activeFocusItem.objectName === "librarySearch" })()""") is True)
    window().grabWindow().save(str(OUT / "library-folder-open.png"))
    click(arrow_point())


def step_arrow_closed():
    c.check("another click closes it", expanded() is False and rows() == c.closed_rows, str(rows()))
    click(name_point())


def step_name():
    c.check("a click on the name chooses it", c.js("tagLibrary.folder") != "", str(c.js("tagLibrary.folder")))
    c.check("...and doesn't open it", expanded() is False)
    QTest.mouseDClick(window(), Qt.LeftButton, Qt.NoModifier, name_point())


def step_double():
    c.check("a double-click on the name opens it", expanded() is True)
    QTest.mouseDClick(window(), Qt.LeftButton, Qt.NoModifier, name_point())


def step_double_again():
    c.check("...and another closes it", expanded() is False)
    # A deep folder doesn't move the tree sideways, and a tilt does.
    c.js("tagLibrary.setFolder(%r)" % DEEP.as_posix())


def step_deep():
    c.check("a deep folder opens the tree down to it",
            tree("tree.rowAtIndex(tagLibrary.folderIndex(tagLibrary.folder))") >= 0)
    c.check("...without moving it sideways", tree("tree.contentX") == 0, str(tree("tree.contentX")))
    found = tree("""(function() {
        var p = tree.mapToItem(null, tree.width / 2, tree.height / 2)
        return [p.x, p.y] })()""")
    c.wheel(found[0], found[1], 0, dx=-120, window=window())


def step_tilted():                       # (the wheel scrolls smoothly, so not at once)
    c.tilted = tree("tree.contentX")
    c.check("a wheel tilt moves it across", c.tilted > 0, str(c.tilted))
    c.js("tagLibrary.setFolder(%r)" % DEEP.parent.as_posix())


def step_stays_across():
    c.check("...and choosing another folder leaves it there", tree("tree.contentX") == c.tilted,
            f'{c.tilted} -> {tree("tree.contentX")}')
    c.finish()


c.run(Scene(), [(800, step_open), (1000, step_arrow), (800, step_arrow_opened), (500, step_arrow_closed),
                (500, step_name), (800, step_double), (800, step_double_again), (1000, step_deep), (1000, step_tilted),
                (600, step_stays_across)])
