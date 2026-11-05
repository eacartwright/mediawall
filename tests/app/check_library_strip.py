"""
The Library's Strip view (readme sections 44.1, 44.4): one large file above
a row of the others, sharing the grid's file list and selection; a video
plays muted with a sound toggle, audio plays with sound, and at most one
file decodes.
"""

import os
import shutil

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from harness import AUDIO, GIF, MOV, OUT, PHOTO, Check, Qt, SCREENSHOT, media
from core.scene import Scene

c = Check("library_strip")

FOLDER = OUT / "mixed"
FOLDER.mkdir(parents=True, exist_ok=True)
for name, source in [("a_photo.jpg", PHOTO), ("b_moving.gif", GIF), ("c_clip.mov", MOV),
                     ("d_song.m4a", AUDIO), ("e_shot.png", SCREENSHOT)]:
    try:
        os.link(media(source), FOLDER / name)
    except OSError:
        shutil.copy(media(source), FOLDER / name)
PHOTO_ROW, GIF_ROW, MOV_ROW, AUDIO_ROW, SHOT_ROW = range(5)


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


def point(object_name, expression):
    found = item(object_name, """(function() {
        var target = %s
        var p = target.mapToItem(null, target.width / 2, target.height / 2)
        return [p.x, p.y] })()""" % expression)
    return QPoint(round(found[0]), round(found[1]))


def key(which, modifiers=Qt.NoModifier):
    if not window().isActive():
        print(f"NOTE  the Library isn't the active window (key {which})", flush=True)
    QTest.keyClick(window(), which, modifiers)


def view(expression):
    """About the large file: `view` is its MediaView (null if there is none)."""
    return item("libraryStripView", "(function() { var view = item.item; return (%s) })()" % expression)


def strip_shown():
    return item("libraryCarousel", "item.visible") is True


def grid_shown():
    return item("libraryGrid", "item.visible") is True


def library_rows():
    c.js("mediaMemory.refresh()")
    return [r for r in c.js("mediaMemory.rows") if r["place"] == "library"]


def step_open():
    c.js("showLibrary()")
    window().requestActivate()
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_grid_first():
    c.check("the Library opens on the grid", grid_shown() and not strip_shown())
    c.check("...with nothing open in the Strip's player", view("view === null") is True)
    QTest.mouseDClick(window(), Qt.LeftButton, Qt.NoModifier,
                      point("libraryGrid", "item.itemAtIndex(%d)" % PHOTO_ROW))


def step_strip_photo():
    c.check("double-clicking a tile opens Strip", strip_shown() and not grid_shown())
    c.check("...on that file", view("view.name") == "a_photo.jpg", str(view("view.name")))
    c.check("the row has every file", item("libraryCarousel", "item.count") == 5)
    c.check("the box still has the focus", item("librarySearch", "item.activeFocus") is True)
    c.check("a picture has no player controls", item("libraryStripControls", "item.visible") is False)
    window().grabWindow().save(str(OUT / "library-strip.png"))
    key(Qt.Key_Right)
    c.check("the thumbnail shows at once, before the file opens", view("view === null") is True)


def step_strip_gif():
    c.check("Right moves to the next file", view("view.name") == "b_moving.gif", str(view("view.name")))
    c.check("...and shares the selection", c.js("tagLibrary.currentRow") == GIF_ROW)
    c.check("an animated GIF plays", view("view.isAnimated && view.playing") is True)
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("Ctrl+Space pauses it", view("view.playing") is False)
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("...and resumes", view("view.playing") is True)
    key(Qt.Key_Right)


def step_strip_video():
    c.check("a video plays, in full", view("view.name") == "c_clip.mov" and view("view.player.playbackState === 1") is True)
    c.check("...muted", view("view.muted") is True)
    c.check("...and it has controls", item("libraryStripControls", "item.visible") is True)
    rows = library_rows()
    c.check("one file decoding, in the Media Memory window", len(rows) == 1, str(rows))
    window().grabWindow().save(str(OUT / "library-strip-video.png"))
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("Ctrl+Space brings up the sound", view("view.muted") is False and view("view.playing") is True)
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("...then pauses", view("view.playing") is False)
    c.check("the controls say so", item("libraryStripControls", "item.playing") is False)
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("...then resumes, still with sound", view("view.playing") is True and view("view.muted") is False)
    key(Qt.Key_Right)


def step_strip_audio():
    c.check("audio plays with sound", view("view.name") == "d_song.m4a" and view("view.muted") is False)
    c.check("...and has controls", item("libraryStripControls", "item.visible") is True)
    rows = library_rows()
    c.check("the file before it has stopped", len(rows) == 1 and rows[0]["name"] == "d_song.m4a", str(rows))
    key(Qt.Key_Left)


def step_sound_kept():
    c.check("back on the video, the sound stays on", view("view.name") == "c_clip.mov" and view("view.muted") is False)
    c.check("...and it isn't paused", view("view.playing") is True)
    c.js("tagLibrary.clickFile(%d, false, false)" % PHOTO_ROW)
    key(Qt.Key_Right)
    key(Qt.Key_Right)
    key(Qt.Key_Right)


def step_held_key():
    c.check("hurrying past files opens only where it stops", view("view.name") == "d_song.m4a", str(view("view.name")))
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier,
                     point("libraryCarousel", "item.itemAtIndex(%d)" % SHOT_ROW))


def step_carousel():
    c.check("a click in the row shows that file", view("view.name") == "e_shot.png", str(view("view.name")))
    QTest.mouseClick(window(), Qt.LeftButton, Qt.ControlModifier,
                     point("libraryCarousel", "item.itemAtIndex(%d)" % PHOTO_ROW))
    c.check("Ctrl+click adds to the selection", c.js("tagLibrary.selectedCount") == 2)
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier,
                     point("libraryCarousel", "item.itemAtIndex(%d)" % SHOT_ROW))
    # Tagging from here.
    c.js("tagLibrary.setQuery('')")
    c.check("tagging works in Strip", c.js("tagLibrary.createAndApply('from strip')") is True)
    c.check("...and shows on the tile", item("libraryCarousel", "item.itemAtIndex(%d).tagged" % SHOT_ROW) is True)
    item("librarySearch", "item.text = 'typing'")
    key(Qt.Key_Escape)
    c.check("Esc clears the box first", item("librarySearch", "item.text") == "" and strip_shown())
    key(Qt.Key_Escape)
    c.check("Esc in an empty box returns to the grid", grid_shown() and not strip_shown())


def step_back_on_grid():
    c.check("...which closes the Strip's player", view("view === null") is True and library_rows() == [])
    c.check("the grid keeps the selection", item("libraryGrid", "item.itemAtIndex(%d).current" % SHOT_ROW) is True)
    item("libraryStripButton", "item.clicked()")


def step_button():
    c.check("the Strip button opens it", strip_shown())
    c.check("...and the box keeps the focus", item("librarySearch", "item.activeFocus") is True)
    item("libraryGridButton", "item.clicked()")
    c.check("the Grid button goes back", grid_shown())
    c.finish()


c.run(Scene(), [
    (800, step_open), (3000, step_grid_first), (700, step_strip_photo), (1500, step_strip_gif),
    (1000, step_strip_video), (800, step_strip_audio), (800, step_sound_kept), (800, step_held_key),
    (700, step_carousel), (500, step_back_on_grid), (400, step_button),
])
