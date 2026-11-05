"""
The Library with animated images, video, and audio (readme section 44.4):
thumbnails and lengths, playing on hover (muted, one at a time), and
Ctrl+Space (with sound). Ends by quitting while thumbnails are still being
made, which run.py's time limit would catch if it hung.
"""

import os
import shutil

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from harness import AUDIO, GIF, MOV, OUT, PHOTO, VIDEO, Check, Qt, media
from bridge.thumbnails import ThumbnailMaker
from core.scene import Scene

c = Check("library_media")


def link(source, target):
    try:
        os.link(source, target)
    except OSError:
        shutil.copy(source, target)


FOLDER = OUT / "mixed"
FOLDER.mkdir(parents=True, exist_ok=True)
for name, source in [("a_photo.jpg", PHOTO), ("b_moving.gif", GIF), ("c_clip.mov", MOV),
                     ("d_long.mp4", VIDEO), ("e_song.m4a", AUDIO)]:
    link(media(source), FOLDER / name)
# A GIF with a single frame, which never plays.
(FOLDER / "f_still.gif").write_bytes(
    b"GIF89a" + (1).to_bytes(2, "little") * 2 + bytes([0x80, 0, 0]) + bytes(6)
    + bytes([0x2C]) + bytes(4) + (1).to_bytes(2, "little") * 2 + bytes([0, 2, 2, 0x44, 1, 0, 0x3B]))
PHOTO_ROW, GIF_ROW, MOV_ROW, MP4_ROW, AUDIO_ROW, STILL_ROW = range(6)

# For the last step: enough videos that some are still waiting when the app quits.
MANY = OUT / "many"
MANY.mkdir(exist_ok=True)
for i in range(40):
    link(media(MOV), MANY / f"{i:03}.mov")


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


def tile(row, role):
    return item("libraryGrid", "item.itemAtIndex(%d).%s" % (row, role))


def tile_point(row):
    found = item("libraryGrid", """(function() {
        var tile = item.itemAtIndex(%d)
        var p = tile.mapToItem(null, tile.width / 2, tile.height / 2)
        return [p.x, p.y] })()""" % row)
    return QPoint(round(found[0]), round(found[1]))


def hover(row):
    QTest.mouseMove(window(), tile_point(row))


def hover_nothing():
    QTest.mouseMove(window(), QPoint(5, 5))


def player(expression):
    return item("libraryPlayer", expression.replace("player.", "item.", 1))


def key(which, modifiers=Qt.NoModifier):
    if not window().isActive():
        print(f"NOTE  the Library isn't the active window (key {which})", flush=True)
    QTest.keyClick(window(), which, modifiers)


def step_open():
    c.js("showLibrary()")
    window().requestActivate()
    c.js("tagLibrary.setFolder(%r)" % str(FOLDER))


def step_tiles():
    c.check("every kind of file is listed", c.js("tagLibrary.files.rowCount()") == 6,
            str(c.js("tagLibrary.files.rowCount()")))
    types = [tile(i, "mediaType") for i in range(6)]
    c.check("each knows its type", types == ["image", "image", "video", "video", "audio", "image"], str(types))

    badges = [tile(i, "badge") for i in range(6)]
    c.check("a still picture has no badge", badges[PHOTO_ROW] == "", badges[PHOTO_ROW])
    c.check("an animated GIF shows its type and length",
            badges[GIF_ROW].startswith("GIF 0:") and badges[GIF_ROW] != "GIF 0:00", badges[GIF_ROW])
    c.check("a video shows its length", badges[MOV_ROW].startswith("0:"), badges[MOV_ROW])
    c.check("...each its own", ":" in badges[MP4_ROW] and badges[MP4_ROW] != badges[MOV_ROW], badges[MP4_ROW])
    c.check("audio shows its length", ":" in badges[AUDIO_ROW], badges[AUDIO_ROW])
    c.check("a GIF with one frame has no badge", badges[STILL_ROW] == "", badges[STILL_ROW])

    for row, label in [(PHOTO_ROW, "a photo"), (GIF_ROW, "a GIF"), (MOV_ROW, "a video"),
                       (MP4_ROW, "a large video"), (STILL_ROW, "a still GIF")]:
        c.check(f"{label} has a thumbnail", str(tile(row, "thumb")).endswith(".jpg"), str(tile(row, "thumb")))
    c.check("audio has no thumbnail, and that isn't a failure",
            tile(AUDIO_ROW, "thumb") == "" and tile(AUDIO_ROW, "failed") is False)
    moves = [tile(i, "moves") for i in range(6)]
    c.check("what moves: the GIF and the videos",
            moves == [False, True, True, True, False, False], str(moves))
    c.check("nothing plays at rest", player("player.row") == -1)
    window().grabWindow().save(str(OUT / "library-media.png"))

    # A new session finds the lengths on disk, without opening the files.
    clip = FOLDER / "c_clip.mov"
    again = ThumbnailMaker(os.environ["MEDIAWALL_THUMBNAILS"])
    c.check("lengths are cached on disk",
            again.duration_ms(str(clip), os.path.getsize(clip), os.path.getmtime(clip)) > 1000)
    again.shutdown()

    hover(PHOTO_ROW)
    hover(GIF_ROW)


def step_hover_waits():
    c.check("hovering doesn't start at once, so crossing tiles starts nothing", player("player.row") == -1)


def step_hover_gif():
    c.check("a hovered GIF plays", player("player.row") == GIF_ROW, str(player("player.row")))
    c.check("...animated", player("player.view.isAnimated") is True and player("player.view.playing") is True)
    hover(MOV_ROW)


def step_hover_video():
    c.check("the next hovered file takes over the one player", player("player.row") == MOV_ROW)
    c.check("...a video, playing", player("player.view.player.playbackState === 1") is True)
    c.check("...muted", player("player.view.muted") is True)
    c.position = player("player.view.position")
    c.js("mediaMemory.refresh()")
    rows = [r for r in c.js("mediaMemory.rows") if r["place"] == "library"]
    c.check("the Media Memory window sees one file decoding", len(rows) == 1, str(rows))
    window().grabWindow().save(str(OUT / "library-hover.png"))


def step_hover_advances():
    c.check("...and moving on", player("player.view.position") > c.position,
            f'{c.position} -> {player("player.view.position")}')
    hover(PHOTO_ROW)


def step_hover_still():
    c.check("hovering a still picture stops it, and plays nothing", player("player.row") == -1)
    hover(STILL_ROW)


def step_hover_still_gif():
    c.check("a still GIF doesn't play", player("player.row") == -1)
    hover(AUDIO_ROW)


def step_hover_audio():
    c.check("audio makes no sound on hover", player("player.row") == -1)
    hover_nothing()
    c.js("tagLibrary.clickFile(%d, false, false)" % AUDIO_ROW)
    key(Qt.Key_Space, Qt.ControlModifier)


def step_play_audio():
    c.check("Ctrl+Space plays the current file", player("player.row") == AUDIO_ROW)
    c.check("...with sound", player("player.withSound") is True and player("player.view.muted") is False)
    c.check("...playing", player("player.view.player.playbackState === 1") is True)
    key(Qt.Key_Space, Qt.ControlModifier)


def step_paused():
    c.check("Ctrl+Space again pauses it", player("player.view.player.playbackState === 2") is True)
    hover(GIF_ROW)


def step_hover_while_playing():
    c.check("hovering doesn't take the player away", player("player.row") == AUDIO_ROW)
    hover_nothing()
    key(Qt.Key_Space, Qt.ControlModifier)


def step_resumed():
    c.check("...and it resumes", player("player.view.player.playbackState === 1") is True)
    key(Qt.Key_Right)


def step_moved_on():
    c.check("moving to the next file stops the sound", player("player.row") == -1)
    c.js("tagLibrary.clickFile(%d, false, false)" % PHOTO_ROW)
    key(Qt.Key_Space, Qt.ControlModifier)
    c.check("Ctrl+Space on a still picture does nothing", player("player.row") == -1)
    c.js("tagLibrary.clickFile(%d, false, false)" % MOV_ROW)
    key(Qt.Key_Space, Qt.ControlModifier)


def step_play_video():
    c.check("a video plays with sound too",
            player("player.row") == MOV_ROW and player("player.view.muted") is False)
    c.js("tagLibrary.setQuery('')")
    c.check("tagging a video works", c.js("tagLibrary.createAndApply('clips')") is True)
    c.check("...and leaves it playing", player("player.row") == MOV_ROW)
    c.js("tagLibrary.setFolder(%r)" % str(MANY))


def step_list_changed():
    c.check("another folder stops it", player("player.row") == -1)
    c.check("the videos are coming", c.js("tagLibrary.files.rowCount()") == 40)
    # Quit with thumbnails still being made: the app must end, cleanly.
    print(f"{sum(c.results)}/{len(c.results)} passed", flush=True)
    c.js("window.close()")


c.run(Scene(), [
    (800, step_open), (5000, step_tiles), (100, step_hover_waits), (1500, step_hover_gif),
    (500, step_hover_video), (800, step_hover_advances), (500, step_hover_still),
    (500, step_hover_still_gif), (500, step_hover_audio), (800, step_play_audio),
    (400, step_paused), (500, step_hover_while_playing), (400, step_resumed), (400, step_moved_on),
    (800, step_play_video), (600, step_list_changed),
])
