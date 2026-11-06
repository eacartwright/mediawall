"""
Clicking media plays and pauses it (readme section 13): free, in a container,
and in a browser's preview. The click that selects doesn't pause; a drag and a
double-click don't either; and neither does anything on a still picture. Also
the wall's toolbar order and minimum size.
"""

from harness import GIF, MEDIA, PHOTO, VIDEO, Check, Qt, media
from core.scene import Scene

c = Check("click_play")

scene = Scene()
gif = scene.add_source(media(GIF), "image", 600, 326)
video = scene.add_source(media(VIDEO), "video", 0, 0)
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)

free_gif = scene.add_media(gif.id, 420, 80)
free_gif.width, free_gif.height = 300, 163
free_photo = scene.add_media(photo.id, 740, 80)
free_photo.width, free_photo.height = 300, 169
free_video = scene.add_media(video.id, 1060, 80)
free_video.width, free_video.height = 200, 200
box = scene.add_object("container", 420, 320, width=300, height=200)
scene.add_media_to_container(gif.id, box.id)

browser = scene.add_object("browser", 760, 320, width=480, height=360)
browser.folder = str(MEDIA)


GIF_SPOT = (570, 160)
PHOTO_SPOT = (890, 160)
VIDEO_SPOT = (1160, 150)
BOX_SPOT = (570, 420)
BOX_EDGE = (570, 325)
PREVIEW_SPOT = (1000, 460)


def content_id():
    return c.scene.content_of(box.id).id


def gif_playing():
    return c.scene.get(free_gif.id).playing


def box_playing():
    return c.scene.get(content_id()).playing


def preview_playing():
    return c.item_js("browserPreview", "item.playing")


def step_start():
    c.check("the free GIF plays, unselected", gif_playing() is True and c.sm.selectedId == "")
    c.click(*GIF_SPOT)


def step_select():
    c.check("the first click selects it", c.sm.selectedId == free_gif.id)
    c.check("...and leaves it playing", gif_playing() is True)
    c.click(*GIF_SPOT)
    c.check("the next pauses it", gif_playing() is False)
    c.check("...which reaches the animation",
            c.js(f"scene.viewFor('{free_gif.id}').animation.playing") is False)
    c.click(*GIF_SPOT)
    c.check("...and the next plays it", gif_playing() is True)


def step_drag():
    c.drag(GIF_SPOT, (GIF_SPOT[0] + 30, GIF_SPOT[1] + 10))
    c.check("a drag moves it", c.scene.get(free_gif.id).x == 450, str(c.scene.get(free_gif.id).x))
    c.check("...and doesn't pause it", gif_playing() is True)
    c.sm.undo()


def step_double_click():
    c.double_click(*GIF_SPOT)


def step_double_clicked():
    c.check("a double-click leaves it playing", gif_playing() is True)
    c.click(*PHOTO_SPOT)
    c.click(*PHOTO_SPOT)
    c.check("a click on a still picture does nothing", c.scene.get(free_photo.id).playing is True)
    c.click(*VIDEO_SPOT)
    c.check("a video's first click selects it", c.sm.selectedId == free_video.id
            and c.scene.get(free_video.id).playing is True)
    c.click(*VIDEO_SPOT)
    c.check("...and the next pauses it", c.scene.get(free_video.id).playing is False)
    c.check("...in its player", c.js(f"scene.viewFor('{free_video.id}').player.playbackState === 2") is True)
    c.click(*VIDEO_SPOT)
    c.check("...and plays it", c.scene.get(free_video.id).playing is True)
    c.click(*BOX_SPOT)


def step_container():
    c.check("in a container too: the first click selects", c.sm.selectedId == box.id and box_playing() is True)
    c.click(*BOX_SPOT)
    c.check("...the next pauses", box_playing() is False)
    c.click(*BOX_EDGE)
    c.check("...the border strip doesn't", box_playing() is False)
    c.click(*BOX_SPOT)
    c.check("...and it plays again", box_playing() is True)
    c.drag(BOX_SPOT, (BOX_SPOT[0] + 40, BOX_SPOT[1]))
    c.check("panning the picture isn't a click", box_playing() is True)
    c.double_click(*BOX_SPOT)


def step_container_double():
    c.check("a double-click leaves it playing", box_playing() is True)
    c.click(*PREVIEW_SPOT)


def step_browser():
    c.check("in a browser: the first click selects", c.sm.selectedId == browser.id and preview_playing() is True)
    c.click(*PREVIEW_SPOT)
    if c.item_js("browserPreview", "item.canPause"):
        c.check("...the next pauses", preview_playing() is False)
        c.click(*PREVIEW_SPOT)
        c.check("...and the next plays", preview_playing() is True)
    else:
        c.check("...a still picture has nothing to pause", preview_playing() is True)
    # Step to the first file that moves, wherever it is in the folder.
    for _ in range(12):
        if c.item_js("browserPreview", "item.type") == "video":
            break
        c.click(*PREVIEW_SPOT, Qt.ForwardButton)
    c.step_type = c.item_js("browserPreview", "item.type")


def step_browser_video():
    c.check("the browser found a video", c.step_type == "video", str(c.step_type))
    c.check("...with Mute but no Pause in its bar",
            c.item_js("browserControls", "item.showMute && item.togglePlay === undefined") is True)
    c.click(*PREVIEW_SPOT)
    c.check("a click pauses it", preview_playing() is False)
    c.win.setProperty("presenting", True)


def step_present():
    c.click(*PREVIEW_SPOT)
    c.check("in Present, where nothing is selected, a click plays it", preview_playing() is True)
    c.click(*GIF_SPOT)
    c.check("...but the canvas stays view-only", gif_playing() is True)
    c.win.setProperty("presenting", False)


def step_toolbar():
    order = [c.center_of(n)[0] for n in ("toolbarSettings", "toolbarAddText", "toolbarLibrary", "toolbarPresent")]
    c.check("the toolbar runs Settings ... Add Text, Library ... Present", order == sorted(order) and order[0] < 80, str(order))
    c.check("Present is at the right-hand end", c.win.width() - order[3] < 80, str(order))
    c.check("Save As is on Save's menu", c.js("saveMenu.itemAt(0).action === appActions.saveAs") is True)
    c.check("the window has a minimum size, for the whole toolbar",
            c.win.minimumWidth() > 500 and c.win.minimumHeight() >= 500,
            f"{c.win.minimumWidth()} x {c.win.minimumHeight()}")
    c.check("...well under the default width", c.win.minimumWidth() < 1100, str(c.win.minimumWidth()))
    c.win.setWidth(100)
    c.win.setHeight(100)


def step_smallest():
    c.check("...which it keeps to", c.win.width() == c.win.minimumWidth()
            and c.win.height() == c.win.minimumHeight(), f"{c.win.width()} x {c.win.height()}")
    last = c.center_of("toolbarPresent")
    c.check("...and every toolbar button is still there",
            last[0] + last[2] / 2 <= c.win.width(), str(last))
    c.grab("wall-smallest.png")
    c.finish()


c.run(scene, [(1500, step_start), (400, step_select), (400, step_drag), (500, step_double_click),
              (600, step_double_clicked), (400, step_container), (600, step_container_double),
              (400, step_browser), (800, step_browser_video), (1000, step_present),
              (800, step_toolbar), (600, step_smallest)])
