"""
Text objects (readme section 5.4): adding one opens the Text tab ready
to type, the box follows the words, Delete while typing edits the words
(not the wall), styles, undo without refitting, and Present.
"""

from PySide6.QtTest import QTest

from harness import Check, Qt
from core.scene import Scene

c = Check("text")

scene = Scene()
existing = scene.add_text(400, 450, "Wall")
existing.width, existing.height = 300, 100


def texts():
    return [o for o in c.scene.objects if o.type == "text"]


def new_text():
    return [o for o in texts() if o.id != existing.id][0]


def aspect(o):
    return o.width / o.height


def natural_aspect(o):
    return c.js(f"window.objectItem('{o.id}').children[0].naturalAspect")


def type_text(text):
    for ch in text:
        QTest.keyClick(c.win, Qt.Key(ord(ch.upper())))


def step_add():
    c.js("appActions.addText.trigger()")


def step_added():
    o = new_text()
    c.check("Add Text adds a text object, selected", len(texts()) == 2
            and c.sm.property("selectedId") == o.id)
    c.check("...and opens the Text tab with the words field focused",
            c.item_js("textTab", "item.checked") is True
            and c.item_js("textField", "item.activeFocus") is True)
    c.check("the new box fits its words", abs(aspect(o) - natural_aspect(o)) < 0.02,
            f"{aspect(o):.3f} vs {natural_aspect(o):.3f}")
    c.width0 = o.width
    type_text("hello wall")


def step_typed():
    o = new_text()
    c.check("typing changes the words", o.text == "hello wall", o.text)
    c.check("...and the box grows to fit them (same height)",
            o.width > c.width0 * 1.5 and abs(aspect(o) - natural_aspect(o)) < 0.02,
            f"{c.width0:.0f} -> {o.width:.0f}")
    c.key(Qt.Key_Delete)                     # cursor at the end: deletes nothing
    c.key(Qt.Key_Backspace)


def step_delete_key():
    o = new_text()
    c.check("Delete/Backspace while typing edit the words, not the wall",
            len(texts()) == 2 and o.text == "hello wal", o.text)
    c.w_before_depth = o.width
    c.sm.setTextStyle(o.id, {"depth": 20, "fill2": "#ff0000", "italic": True})


def step_styled():
    o = new_text()
    c.check("a style change is stored", o.text_style["depth"] == 20 and o.text_style["italic"])
    c.check("...and the box follows the new proportions", o.width != c.w_before_depth)
    c.grab("text.png")
    c.sm.undo()


def step_undone():
    o = new_text()
    c.check("undo reverts the style and the box together",
            o.text_style["depth"] == 0 and abs(o.width - c.w_before_depth) < 0.5)
    c.check("...and nothing refits after undo (redo still available)", c.sm.property("canRedo"))
    while c.sm.property("canUndo"):
        c.sm.undo()
    c.check("undoing everything removes the added text", len(texts()) == 1)
    c.win.setProperty("presenting", True)


def step_present():
    c.click(550, 500)
    c.check("Present: text can't be selected", c.sm.property("selectedId") == "")
    c.key(Qt.Key_Escape)
    c.finish()


c.run(scene, [(1500, step_add), (500, step_added), (600, step_typed), (400, step_delete_key),
              (500, step_styled), (500, step_undone), (800, step_present)])
