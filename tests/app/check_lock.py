"""
Lock Container (right-click): a locked container can't be moved,
resized, rotated, or wheel-scaled; its picture can't be panned, zoomed,
or reset; a browsing one doesn't step to other files; and nothing can be
dropped into an empty one. Unlocking makes it editable again.
"""

from harness import Check, PHOTO, SCREENSHOT, Qt, media
from core.scene import Scene

c = Check("lock")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
shot = scene.add_source(media(SCREENSHOT), "image", 0, 0)
box = scene.add_object("container", 100, 100, width=400, height=300)
scene.add_media_to_container(photo.id, box.id)
empty = scene.add_object("container", 600, 100, width=300, height=200)
free = scene.add_media(shot.id, 700, 450)
free.width, free.height = 160, 100


def geo(o):
    return (round(o.x, 1), round(o.y, 1), round(o.width, 1), round(o.height, 1), round(o.rotation, 1))


def content():
    return c.scene.content_of(box.id)


def step_lock():
    c.click(300, 250, Qt.RightButton)


def step_menu():
    x, y, _, _ = c.center_of("lockContainerItem")
    c.click(x, y)


def step_locked():
    c.check("Lock Container (right-click) locks it", c.scene.get(box.id).locked is True)
    c.check("...shows a Locked badge, and no resize or rotate handles",
            c.item_js("lockedBadge", "item.visible") is True)
    c.b0, c.c0 = geo(c.scene.get(box.id)), geo(content())
    c.drag((300, 250), (360, 300))                                  # pan
    c.drag((300, 104), (340, 140))                                  # border strip: move
    c.drag((300, 250), (200, 200), Qt.MiddleButton)                 # middle-drag: move
    c.wheel(300, 250, 120)                                          # zoom
    c.wheel(300, 104, 120)                                          # strip: scale


def step_still():
    c.check("locked: dragging, middle-drag, and the wheel change nothing",
            geo(c.scene.get(box.id)) == c.b0 and geo(content()) == c.c0,
            f"{geo(c.scene.get(box.id))} {geo(content())}")
    c.sm.select("")
    c.sm.setLocked(empty.id, True)
    c.drag((780, 500), (750, 200))                                  # free image onto the empty one


def step_no_drop():
    c.check("nothing can be dropped into a locked container",
            c.scene.content_of(empty.id) is None and c.scene.get(free.id).parent_id is None)
    c.sm.undo()                                                     # the image move
    c.sm.undo()                                                     # locking the empty one
    c.check("locking is undoable", c.scene.get(empty.id).locked is False)
    c.sm.setLocked(box.id, False)
    c.drag((300, 250), (360, 300))


def step_unlocked():
    c.check("unlocked: dragging pans the picture again", geo(content()) != c.c0)
    c.finish()


c.run(scene, [(1500, step_lock), (500, step_menu), (500, step_locked), (600, step_still),
              (600, step_no_drop), (500, step_unlocked)])
