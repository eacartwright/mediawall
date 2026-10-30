"""
Text animations (readme section 5.4): each one chosen in the Text tab
moves or changes the canvas text over time (Wiggle turns it, Pulse
scales it, Glow pulse fades the glow, Gradient shift slides the fill,
Color cycle turns its hue); the preset tiles stay still; Speed sets the
cycle; undo brings the old setting back; None stops it.
"""

from PySide6.QtCore import QTimer

from harness import OUT, Check
from core.scene import Scene

c = Check("text_animation")

scene = Scene()
text = scene.add_text(300, 300, "Wave", {"glow": 10, "fill": "#ff8020", "fill2": "#2040ff"})
text.width, text.height = 400, 150

ART = f"window.objectItem('{text.id}').children[0]"

# A descendant of the canvas text with this objectName.
FIND = """(function find(item, name) {
    if (item.objectName === name) return item
    for (var i = 0; i < item.children.length; i++) {
        var f = find(item.children[i], name)
        if (f) return f
    }
    return null
})"""

# What each animation changes, as an expression.
WATCH = {
    "wiggle": f"{FIND}({ART}, 'textMotion').rotation",
    "pulse": f"{FIND}({ART}, 'textMotion').scale",
    "glow_pulse": f"{FIND}({ART}, 'glowLoader').opacity",
    # The face's gradient: the shape (beside its Repeater) that has one.
    "gradient_shift": f"""(function() {{ var k = {FIND}({ART}, 'textFace').parent.children
        for (var i = 0; i < k.length; i++)
            if (k[i].fillGrad) return k[i].fillGrad.y1 }})()""",
    "color_cycle": f"{ART}.faceFill.toString()",
}
ORDER = ["", "wiggle", "pulse", "glow_pulse", "gradient_shift", "color_cycle"]


def style():
    return c.scene.get(text.id).text_style


def choose(box, index):
    c.item_js(box, f"item.activated({index})")


def sample(expression):
    c.samples = []
    for t in range(0, 600, 60):
        QTimer.singleShot(t, lambda: c.samples.append(c.js(expression)))
    # What's on screen, twice: the drawing itself has to change, not
    # only the values it's drawn from.
    c.shots = []
    for t in (150, 450):
        QTimer.singleShot(t, lambda: c.shots.append(text_on_screen()))


def text_on_screen():
    x, y, w, h = c.js(f"""(function() {{ var p = {ART}.mapToItem(null, 0, 0)
        return [p.x, p.y, {ART}.width, {ART}.height] }})()""")
    return c.win.grabWindow().copy(round(x), round(y), round(w), round(h))


def step_open():
    c.js(f"scene.textEditRequested('{text.id}')")


def step_still():
    c.check("no animation: the canvas text is still", c.js(f"{ART}.running") is False)
    c.check("...and Speed is off", c.item_js("animationSpeedBox", "item.enabled") is False)
    start("wiggle")


def start(name):
    choose("animationBox", ORDER.index(name))
    c.current = name
    sample(WATCH[name])


def checker(name, following):
    def step():
        varied = len({round(v, 3) if isinstance(v, float) else v for v in c.samples})
        c.check(f"{name}: chosen in the Text tab, it changes the canvas text over time",
                style()["animation"] == name and varied >= 3, f"{style()['animation']}: {c.samples}")
        c.check("...and it's redrawn", len(c.shots) == 2 and c.shots[0] != c.shots[1])
        c.shots[-1].save(str(OUT / f"text-{name}.png"))
        following()
    return step


def after_wiggle():
    tile = c.item_js("presetSunset", "item.children[0].running")
    c.check("...the preset tiles stay still", tile is False, str(tile))
    start("pulse")


def step_speed():
    choose("animationSpeedBox", 2)
    c.check("Speed: Fast makes a cycle 1.5 s",
            style()["animation_speed"] == "fast" and c.js(f"{ART}.cycleMs") == 1500)
    c.sm.undo()
    c.check("undo brings back Normal, in the Text tab too",
            style()["animation_speed"] == "normal"
            and c.item_js("animationSpeedBox", "item.currentText") == "Normal")
    choose("animationBox", 0)
    c.check("None: the text stops, back to still",
            style()["animation"] == "" and c.js(f"{ART}.running") is False
            and c.js(f"{ART}.phase") == 0 and c.js(WATCH["wiggle"]) == 0)
    c.finish()


c.run(scene, [(1500, step_open), (400, step_still),
              (800, checker("wiggle", after_wiggle)),
              (800, checker("pulse", lambda: start("glow_pulse"))),
              (800, checker("glow_pulse", lambda: start("gradient_shift"))),
              (800, checker("gradient_shift", lambda: start("color_cycle"))),
              (800, checker("color_cycle", lambda: None)),
              (200, step_speed)])
