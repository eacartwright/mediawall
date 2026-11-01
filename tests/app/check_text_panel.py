"""
The Text tab (readme section 5.4): its controls fit the panel (Wrap to
box's alignment buttons included), and the mouse wheel over the words
field moves the cursor along a long line, 3 letters a notch.
"""

from harness import Check, Qt
from core.scene import Scene

c = Check("text_panel")

scene = Scene()
words = "A long line of words, much longer than the Text tab's field is wide"
text = scene.add_text(600, 300, words)
text.width, text.height = 500, 80
text.text_style["wrap"] = True                 # shows Left / Center / Right


def step_select():
    c.sm.select(text.id)
    c.open_sidebar()


def step_tab():
    c.choose_tab("textTab")


def step_fits():
    x, _, w, _ = c.center_of("textField")
    panel_width = 280                          # Sidebar.qml's panelWidth
    c.check("the Text tab's controls fit the panel, with a margin on the right",
            x + w / 2 <= panel_width - 6, f"right edge {x + w / 2:.0f} of {panel_width}")
    x, y, _, _ = c.center_of("textField")
    c.click(x, y)
    c.key(Qt.Key_End)


def step_wheel_back():
    x, y, _, _ = c.center_of("textField")
    for _ in range(5):
        c.wheel(x, y, 120)                     # up: back along the line
    c.check("the wheel moves the cursor back along a long line",
            c.item_js("textField", "item.cursorPosition") == len(words) - 15,
            str(c.item_js("textField", "item.cursorPosition")))
    for _ in range(2):
        c.wheel(x, y, -120)                    # down: forward
    c.check("...and forward", c.item_js("textField", "item.cursorPosition") == len(words) - 9,
            str(c.item_js("textField", "item.cursorPosition")))
    c.check("...without changing the words", c.scene.get(text.id).text == words)
    c.finish()


c.run(scene, [(1500, step_select), (600, step_tab), (600, step_fits), (400, step_wheel_back)])
