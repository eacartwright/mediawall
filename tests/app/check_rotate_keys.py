"""
Up / Down turn the picture a quarter turn (readme section 49): a free
image turns around its center; in a container the picture turns and the
container stays as it is (a fitted picture is fitted again). Undoable,
and not while typing in a field.
"""

from harness import PHOTO, Check, Qt, media
from core.scene import Scene

c = Check("rotate_keys")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
free = scene.add_media(photo.id, 300, 400)
free.width, free.height = 320, 180
box = scene.add_object("container", 700, 150, width=400, height=300)
content, _ = scene.add_media_to_container(photo.id, box.id)
text = scene.add_text(300, 150, "Words")
text.width, text.height = 200, 60


def get(object_id):
    return c.scene.get(object_id)


def inside():
    return c.scene.content_of(box.id)


def step_select_free():
    c.sm.select(free.id)


def step_up():
    c.key(Qt.Key_Up)


def step_free_turned():
    o = get(free.id)
    c.check("Up turns a free image a quarter turn clockwise, in place",
            o.rotation == 90 and (o.x, o.y, o.width, o.height) == (300, 400, 320, 180),
            f"{o.rotation}")
    c.key(Qt.Key_Down)
    c.key(Qt.Key_Down)


def step_free_back():
    c.check("Down turns it back the other way", get(free.id).rotation == 270,
            str(get(free.id).rotation))
    c.sm.undo()


def step_free_undone():
    c.check("each turn is one undo step (270 back to 0)", get(free.id).rotation == 0,
            str(get(free.id).rotation))
    c.sm.select(box.id)
    c.before = (inside().width, inside().height)


def step_box_up():
    c.key(Qt.Key_Up)


def step_box_turned():
    b, i = get(box.id), inside()
    c.check("in a container, Up turns the picture...", i.rotation == 90, str(i.rotation))
    c.check("...and the container stays as it is",
            (b.x, b.y, b.width, b.height, b.rotation) == (700, 150, 400, 300, 0))
    # Fit: sideways, the whole picture shows, as tall as the container.
    c.check("...and a fitted picture is fitted again (shown whole)",
            abs(i.width - 300) < 0.5 and i.height < 300, f"{i.width:.0f} x {i.height:.0f}")
    c.sm.select(free.id)
    # Any field with a cursor (the Speech tab's words, a number box...):
    # a stand-in one, so this doesn't depend on a tab's state.
    c.js("Qt.createQmlObject('import QtQuick; TextInput { objectName: \"stand-in\"; "
         "width: 100; height: 20 }', window.contentItem).forceActiveFocus()")


def step_typing():
    c.typing_focus = c.item_js("stand-in", "item.activeFocus")
    c.key(Qt.Key_Up)


def step_typing_ignored():
    c.check("not while typing in a field",
            c.typing_focus is True and c.sm.property("selectedId") == free.id
            and get(free.id).rotation == 0,
            f"focus {c.typing_focus}, {get(free.id).rotation}")
    c.finish()


c.run(scene, [(1500, step_select_free), (300, step_up), (300, step_free_turned),
              (300, step_free_back), (300, step_free_undone), (300, step_box_up),
              (300, step_box_turned), (400, step_typing),
              (300, step_typing_ignored)])
