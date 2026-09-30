"""
The Layers panel (readme section 23): listing and names, selecting from
the list, the arrange buttons, and drag-to-reorder.
"""

from harness import Check, PHOTO, VIDEO, MEDIA, media
from core.scene import Scene

c = Check("layers")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
video = scene.add_source(media(VIDEO), "video", 0, 0)
free = scene.add_media(photo.id, 60, 120)
browser = scene.add_object("browser", 420, 90, width=440, height=340)
browser.folder = str(MEDIA)
box = scene.add_object("container", 80, 420, width=300, height=200)
scene.add_media_to_container(photo.id, box.id)
clip = scene.add_media(video.id, 500, 470)
empty = scene.add_object("container", 900, 520, width=200, height=140)


def names():
    return [l["name"] for l in c.sm.property("layers")]


def order():
    return [o.id for o in c.scene.layer_order()]


def row(i):
    """Window position of the middle of Layers row i."""
    x, y, w, h = c.center_of("layerList")
    top = y - h / 2
    return x, top + 30 * i + 15


def step_open():
    c.check("listed top first, browsers on top", names() == [
        "Browser · MEDIATEST", "Container (empty)", VIDEO, "Container · " + PHOTO, PHOTO], str(names()))
    c.open_sidebar()


def step_select():
    c.choose_tab("layersTab")
    c.click(*row(2))
    c.check("clicking a row selects that object", c.sm.property("selectedId") == clip.id)


def step_arrange():
    x, y, w, h = c.center_of("layerList")
    # The arrange buttons sit below the list: Top | Up | Down | Bottom.
    c.click(x - w / 2 + w * 3 / 8, y + h / 2 + 20)                  # Up
    c.check("Up moves it above the empty container", names()[1] == VIDEO, str(names()[:3]))
    c.check("it's now at the front of its group (the browser stays above)",
            c.sm.property("selectedAtFront") and names()[0].startswith("Browser"))


def step_drag():
    c.before = order()
    x, _ = row(0)
    c.drag(row(4), (x, row(0)[1] - 16))                             # bottom row to the top of its group
    after = order()
    c.check("dragging the bottom row up moves it to the top of its group",
            after[1] == c.before[4] and after[0] == browser.id, str([c.before.index(i) for i in after]))
    c.sm.undo()
    c.check("one drag is one undo step", order() == c.before)


def step_browser():
    c.sm.select(browser.id)
    c.check("a lone browser is at the front and back of its group",
            c.sm.property("selectedAtFront") and c.sm.property("selectedAtBack"))
    c.finish()


c.run(scene, [(1500, step_open), (1000, step_select), (1000, step_arrange),
              (1000, step_drag), (1000, step_browser)])
