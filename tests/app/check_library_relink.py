"""
Moved and missing files in the Library (readme section 44.6): a moved file
gets its tags back when its new folder is opened, and Clean Up asks before
forgetting the tags of what's missing.
"""

import os
import shutil

from harness import OUT, PHOTO, Check, SCREENSHOT, media
from core.scene import Scene

c = Check("library_relink")

FOLDER = OUT / "media"
(FOLDER / "old").mkdir(parents=True, exist_ok=True)
(FOLDER / "new").mkdir(exist_ok=True)
MOVER = FOLDER / "old" / "moves.jpg"
GONE = FOLDER / "old" / "gone.png"
STAYS = FOLDER / "old" / "stays.png"
shutil.copy(media(PHOTO), MOVER)
shutil.copy(media(SCREENSHOT), GONE)
# Not an identical copy of the one that goes.
shutil.copy(media(PHOTO), STAYS.with_suffix(".jpg"))
with open(STAYS.with_suffix(".jpg"), "ab") as f:
    f.write(b"different")
STAYS = STAYS.with_suffix(".jpg")


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


def names():
    return sorted(c.js("tagLibrary.fileAt(%d).name" % i) for i in range(c.js("tagLibrary.files.rowCount()")))


def message():
    return item("libraryMessage", "item.text")


def dialog(expression):
    return c.js("(function() { var item = libraryLoader.item.cleanUp; return (%s) })()" % expression)


def step_open():
    c.js("showLibrary()")
    window().requestActivate()
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER / "old"))


def step_tag():
    c.js("tagLibrary.selectAll()")
    c.js("tagLibrary.createAndApply('kept')")
    c.check("three files tagged", c.js("tagLibrary.selectedCount") == 3)
    os.replace(MOVER, FOLDER / "new" / "moved.jpg")
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER / "new"))


def step_moved():
    c.check("its new folder lists it", names() == ["moved.jpg"], str(names()))
    c.check("...with its tags", item("libraryGrid", "item.itemAtIndex(0).tagged") is True)
    c.check("the status bar says so", "1 moved file" in message(), message())
    rows = c.js("tagLibrary.selectionTags")
    c.check("the file shows the tag", [r["name"] for r in rows] == ["kept"], str(rows))
    GONE.unlink()
    c.js("tagLibrary.startCleanUp()")


def step_asks():
    c.check("Clean Up asks first", dialog("item.opened") is True)
    c.check("...how many", dialog("item.count") == 1)
    c.check("...and where", dialog("item.where").endswith("(1)") and "old" in dialog("item.where"), dialog("item.where"))
    window().grabWindow().save(str(OUT / "library-cleanup.png"))
    dialog("item.reject()")


def step_refused():
    c.js("tagLibrary.findMode = true")


def step_still_found():
    c.check("cancelling keeps them: still found, as missing", "gone.png" in names(), str(names()))
    c.check("...nothing else is missing", c.js("tagLibrary.fileCount") == 3)
    c.js("tagLibrary.startCleanUp()")


def step_asks_again():
    dialog("item.accept()")


def step_cleaned():
    c.check("accepting forgets the missing file", "gone.png" not in names(), str(names()))
    c.check("...and only that", names() == ["moved.jpg", "stays.jpg"], str(names()))
    c.check("...and says so", "1 missing file" in message(), message())
    c.js("tagLibrary.startCleanUp()")


def step_nothing_left():
    c.check("with nothing missing, it just says so", dialog("item.opened") is False and "No files" in message(), message())
    c.finish()


c.run(Scene(), [
    (800, step_open), (800, step_tag), (1000, step_moved), (800, step_asks), (500, step_refused),
    (800, step_still_found), (800, step_asks_again), (500, step_cleaned), (800, step_nothing_left),
])
