"""
The Text tab's list and Lock (readme section 5.4): every text object has
a line (click to select), the tab's Add Text button shows only while
there's no text, and a locked text ignores the mouse, so a click on it
reaches the container behind. Lock is undoable.
"""

from harness import PHOTO, Check, media
from core.scene import Scene

c = Check("text_lock")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
box = scene.add_object("container", 500, 150, width=400, height=300)
scene.add_media_to_container(photo.id, box.id)
over = scene.add_text(550, 260, "Over the picture")
over.width, over.height = 300, 80
other = scene.add_text(500, 550, "Another line")
other.width, other.height = 240, 60


def item(object_id, expr):
    return c.js(f"window.objectItem('{object_id}').{expr}")


def click_item(object_name):
    x, y, _, _ = c.center_of(object_name)
    c.click(x, y)


def step_open():
    c.open_sidebar()


def step_tab():
    c.choose_tab("textTab")


def step_list():
    c.check("each text has a line in the Text tab",
            c.center_of("textRow:" + over.id) is not None
            and c.center_of("textRow:" + other.id) is not None)
    c.check("...and the tab's Add Text button is gone", c.center_of("addTextButton") is None)
    click_item("textRow:" + other.id)


def step_selected():
    c.check("clicking a line selects its text", c.sm.property("selectedId") == other.id)
    click_item("textLock:" + over.id)


def step_locked():
    c.check("Lock locks the text", c.scene.get(over.id).locked is True)
    c.check("...which then ignores the mouse", item(over.id, "enabled") is False)
    c.click(700, 300)                                   # on the locked text
    c.check("a click on locked text reaches the container behind it",
            c.sm.property("selectedId") == box.id, str(c.sm.property("selectedId")))
    click_item("textRow:" + over.id)


def step_locked_selected():
    c.grab("text-lock.png")
    c.check("locked text can still be selected from the tab",
            c.sm.property("selectedId") == over.id)
    c.sm.setTextStyle(over.id, {"italic": True})
    c.check("...and its style changed there", c.scene.get(over.id).text_style["italic"] is True)
    c.sm.undo()
    c.sm.undo()


def step_undone():
    c.check("undo unlocks it", c.scene.get(over.id).locked is False
            and item(over.id, "enabled") is True)
    c.sm.removeObject(over.id)
    c.sm.removeObject(other.id)


def step_no_text():
    c.check("with no text left, the tab's Add Text button is back",
            c.center_of("addTextButton") is not None)
    c.finish()


c.run(scene, [(1500, step_open), (500, step_tab), (500, step_list), (300, step_selected),
              (400, step_locked), (400, step_locked_selected), (400, step_undone),
              (400, step_no_text)])
