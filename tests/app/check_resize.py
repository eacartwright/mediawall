"""
Resizing and scaling (readme sections 5, 6.4): edge handles (also on
rotated containers and images), double-click edge fill, wheel scaling
of free images and containers, and zoom in Adjust mode.
"""

import math

from harness import Check, PHOTO, Qt, media
from core.scene import Scene

c = Check("resize")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
box = scene.add_object("container", 100, 150, width=300, height=200)
tilted = scene.add_object("container", 600, 150, width=300, height=200)
tilted.rotation = 30
picture = scene.add_media(photo.id, 300, 480)
picture.width, picture.height = 320, 180
above = scene.add_object("container", 50, 20, width=500, height=60)          # neighbour for edge fill
full = scene.add_object("container", 950, 480, width=240, height=160)
scene.add_media_to_container(photo.id, full.id)
full.lock_content = False


def get(o):
    return c.scene.get(o.id)


def rot(x, y, deg):
    r = math.radians(deg)
    return x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)


def mid_left(o):
    cx, cy = o.x + o.width / 2, o.y + o.height / 2
    d = rot(-o.width / 2, 0, o.rotation)
    return cx + d[0], cy + d[1]


def step_edges():
    c.sm.select(box.id)
    o = get(box)
    left0 = mid_left(o)
    c.drag((o.x + o.width - 6, o.y + o.height / 2), (o.x + o.width + 54, o.y + o.height / 2))
    o = get(box)
    c.check("right edge bar: wider, same height", (round(o.width), round(o.height)) == (360, 200))
    c.check("...and the left side stays put", all(abs(a - b) < 1 for a, b in zip(mid_left(o), left0)))
    c.sm.select(tilted.id)


def step_tilted():
    o = get(tilted)
    left0 = mid_left(o)
    cx, cy = o.x + o.width / 2, o.y + o.height / 2
    grab = rot(o.width / 2 - 6, 0, o.rotation)
    step = rot(60, 0, o.rotation)
    c.drag((cx + grab[0], cy + grab[1]), (cx + grab[0] + step[0], cy + grab[1] + step[1]))
    o = get(tilted)
    c.check("rotated container: the edge moves along its own axis", (round(o.width), round(o.height)) == (360, 200))
    c.check("...with the other side fixed", all(abs(a - b) < 1.5 for a, b in zip(mid_left(o), left0)))
    c.sm.select(picture.id)


def step_image():
    o = get(picture)
    aspect = o.width / o.height
    c.drag((o.x + o.width / 2, o.y + o.height - 6), (o.x + o.width / 2, o.y + o.height + 39))
    o = get(picture)
    c.check("image bottom edge: taller, aspect kept", abs(o.height - 225) < 1.5 and abs(o.width / o.height - aspect) < 0.01)
    w0 = o.width
    c.drag((o.x + o.width - 8, o.y + o.height - 8), (o.x + o.width + 32, o.y + o.height + 32))
    c.check("the corner handle still resizes", get(picture).width > w0 + 20)
    # wheel scaling of a selected free image
    o = get(picture)
    cx, cy, w0 = o.x + o.width / 2, o.y + o.height / 2, o.width
    c.wheel(cx, cy, 120)
    step = c.js("appSettings.zoomStep") / 100
    o = get(picture)
    c.check("wheel scales a selected image by the zoom step, around the pointer",
            abs(o.width / w0 - (1 + step)) < 1e-3 and abs(o.x + o.width / 2 - cx) < 0.5)
    c.sm.select(box.id)


def step_fill():
    c.sm.undo(); c.sm.undo(); c.sm.undo(); c.sm.undo()               # back to the box's original size
    c.sm.select(box.id)
    o = get(box)
    c.double_click(o.x + o.width / 2, o.y + o.height - 5)           # bottom edge bar


def step_fill2():
    o = get(box)
    below = get(picture)                                            # in the same column, below
    c.check("double-click on the bottom edge: fills between the neighbours above and below",
            (round(o.y), round(o.y + o.height)) == (80, round(below.y)), f"{o.y:.0f}..{o.y + o.height:.0f}")
    c.sm.undo()
    c.check("one undo puts it back", (round(get(box).y), round(get(box).height)) == (150, 200))
    c.sm.select(full.id)


def step_container_wheel():
    c.sm.select("")                                                 # none of this needs a selection
    o, content = get(full), c.scene.content_of(full.id)
    w0, cw0, cx0 = o.width, content.width, content.x
    c.wheel(o.x + 4, o.y + o.height / 2, 120)                       # on the border strip
    step = c.js("appSettings.zoomStep") / 100
    o, content = get(full), c.scene.content_of(full.id)
    c.check("wheel on the border strip scales the container with its content (even unlocked)",
            abs(o.width / w0 - (1 + step)) < 1e-3 and abs(content.width / cw0 - (1 + step)) < 1e-3
            and abs(content.x - cx0 * (1 + step)) < 0.5)
    w0, cw0 = o.width, content.width
    c.wheel(o.x + o.width / 2, o.y + o.height / 2, 120)             # inside
    c.check("wheel inside zooms only the picture (not browsing, not selected)",
            get(full).width == w0 and abs(c.scene.content_of(full.id).width / cw0 - (1 + step)) < 1e-3)
    o, content = get(full), c.scene.content_of(full.id)
    x0, cx0 = o.x, content.x
    c.drag((o.x + o.width / 2, o.y + o.height / 2), (o.x + o.width / 2 - 30, o.y + o.height / 2))
    c.check("left-drag inside pans the picture; the container stays",
            get(full).x == x0 and abs(c.scene.content_of(full.id).x - (cx0 - 30)) < 0.5)
    c.sm.undo()
    c.check("...undoably", abs(c.scene.content_of(full.id).x - cx0) < 0.5)
    e = get(box)                                                    # empty
    w0 = e.width
    c.sm.select("")
    c.wheel(e.x + e.width / 2, e.y + e.height / 2, 120)
    c.check("an empty container scales from anywhere, unselected",
            abs(get(box).width / w0 - (1 + step)) < 1e-3, f"{get(box).width:.0f} vs {w0:.0f}")
    c.sm.undo()
    c.sm.select(full.id)


def knob(o):
    return o.x + o.width / 2, o.y - 14                              # above the top edge's middle


def step_ctrl_knob():
    o = get(full)
    r0, cr0 = o.rotation, c.scene.content_of(full.id).rotation
    c.drag(knob(o), (o.x + o.width, o.y + o.height / 2), modifiers=Qt.ControlModifier)
    r1, cr1 = get(full).rotation, c.scene.content_of(full.id).rotation
    c.check("Ctrl + knob turns the picture, not the container",
            r1 == r0 and abs(cr1 - cr0) > 30, f"{r1}, {cr1:.0f}")
    c.sm.undo()
    c.sm.adjustRequested.emit(full.id)


def step_adjust():
    o = get(full)
    r0, cr0 = o.rotation, c.scene.content_of(full.id).rotation
    c.drag(knob(o), (o.x + o.width, o.y + o.height / 2))
    r1, cr1 = get(full).rotation, c.scene.content_of(full.id).rotation
    c.check("in Adjust mode the knob turns the picture",
            r1 == r0 and abs(cr1 - cr0) > 30, f"{r1}, {cr1:.0f}")
    c.key(Qt.Key_Return)
    c.finish()


c.run(scene, [(1500, step_edges), (1000, step_tilted), (1000, step_image), (1000, step_fill),
              (1000, step_fill2), (1000, step_container_wheel), (1000, step_ctrl_knob),
              (1000, step_adjust)])
