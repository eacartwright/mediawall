"""
Text objects (readme section 5.4): adding one (toolbar) opens a field on
the canvas ready to type, the box follows the words, Delete while typing
edits the words (not the wall), styles, undo without refitting, wrap
(the height follows the lines), arc, the font list, double-click to type,
and Present.
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
    spot = c.center_of("toolbarAddText")
    c.click(spot[0], spot[1])


def step_added():
    o = new_text()
    c.check("Add Text adds a text object, selected", len(texts()) == 2
            and c.sm.property("selectedId") == o.id)
    c.check("...shows the Text tab, and types on the canvas",
            c.item_js("textTab", "item.checked") is True
            and c.item_js("canvasTextField", "item.activeFocus") is True)
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
    # Wrap: the existing text, made longer, wraps at the box's width.
    c.sm.select(existing.id)
    c.sm.setText(existing.id, "a wall of words that wraps onto lines")


def step_wrap_on():
    o = c.scene.get(existing.id)
    o_width = o.width
    c.js(f"(function() {{ var t = window.objectItem('{existing.id}'); t.width = {o.width / 3}; t.commit() }})()")
    c.js(f"window.objectItem('{existing.id}').setWrap(true)")
    c.wrap_width = c.scene.get(existing.id).width
    c.check("(the box fitted the long line first)", o_width > 1000, f"{o_width:.0f}")


def step_wrapped():
    o = c.scene.get(existing.id)
    lines = c.js(f"window.objectItem('{existing.id}').children[0].shaped.lines")
    c.check("wrap on: the width stays, the words wrap, the height follows the lines",
            o.text_style["wrap"] and abs(o.width - c.wrap_width) < 0.5 and lines >= 2
            and abs(o.height - c.js(f"window.objectItem('{existing.id}').children[0].wrappedHeight")) < 0.5,
            f"{o.width:.0f} x {o.height:.0f}, {lines} lines")
    c.h_wrapped = o.height
    # Narrower box (as a resize does): more lines, a taller box.
    c.js(f"(function() {{ var t = window.objectItem('{existing.id}'); t.width = {o.width / 2}; t.commit() }})()")


def step_rewrapped():
    o = c.scene.get(existing.id)
    c.check("resizing narrower rewraps: taller box", o.height > c.h_wrapped * 1.4,
            f"{c.h_wrapped:.0f} -> {o.height:.0f}")
    c.sm.setTextStyle(existing.id, {"arc": 120})
    c.h_before_arc = o.height


def step_arc():
    o = c.scene.get(existing.id)
    c.check("an arc is stored and the box refits", o.text_style["arc"] == 120.0
            and abs(o.height - c.h_before_arc) > 1, f"{c.h_before_arc:.0f} -> {o.height:.0f}")
    c.grab("text-wrap-arc.png")
    c.js(f"window.objectItem('{existing.id}').setWrap(false)")
    c.sm.setTextStyle(existing.id, {"arc": 0})


def step_unwrapped():
    o = c.scene.get(existing.id)
    c.check("wrap off: one line again, as tall as one line", not o.text_style["wrap"]
            and o.width > o.height * 3, f"{o.width:.0f} x {o.height:.0f}")
    # Font list: type to find, Enter picks.
    c.js(f"scene.textEditRequested('{existing.id}')")


def step_open_fonts():
    spot = c.center_of("fontPicker")
    c.click(spot[0], spot[1])


def step_font():
    count = c.item_js("fontList", "item.count")
    type_text("ari")
    c.check("the font list shows the installed fonts", count and count > 2, str(count))
    c.found = c.item_js("fontList", "item.count")
    c.key(Qt.Key_Down)
    c.key(Qt.Key_Return)


def step_font2():
    font = c.scene.get(existing.id).text_style["font"]
    c.check("typing filters the fonts, and Enter picks one",
            c.found is not None and c.found < 50 and "ari" in font.lower(), f"{c.found}: {font}")
    o = c.scene.get(existing.id)
    c.sm.select("")
    c.double_click(o.x + o.width / 2, o.y + o.height / 2)


def step_double_click():
    c.check("double-click types on the canvas",
            c.item_js("canvasTextField", "item.activeFocus") is True)
    c.key(Qt.Key_Escape)
    c.sm.setTextStyle(existing.id, {"glow": 12})


def step_glow():
    # Turned on after loading (it once only showed when loaded with one).
    c.check("glow turned on later draws its effect",
            c.js(f"""(function() {{ var k = window.objectItem('{existing.id}').children[0].children[0].children
                for (var i = 0; i < k.length; i++)
                    if (k[i].objectName === 'glowLoader') return k[i].item !== null
                return false }})()""") is True)
    c.win.setProperty("presenting", True)


def step_present():
    c.click(550, 500)
    c.check("Present: text can't be selected", c.sm.property("selectedId") == "")
    c.key(Qt.Key_Escape)
    c.finish()


c.run(scene, [(1500, step_add), (500, step_added), (600, step_typed), (400, step_delete_key),
              (500, step_styled), (500, step_undone), (400, step_wrap_on), (500, step_wrapped), (400, step_rewrapped),
              (400, step_arc), (400, step_unwrapped), (400, step_open_fonts), (600, step_font), (500, step_font2),
              (600, step_double_click), (400, step_glow), (800, step_present)])
