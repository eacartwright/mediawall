"""
Text animations (readme section 5.4): each one ticked in the Text tab
moves or changes the canvas text over time (Wiggle turns it, Pulse
scales it, Ripple grows the letters in turn, Fade fades it, Glow pulse
fades the glow, Gradient shift slides the fill, Color cycle turns its
hue); several run together; the preset tiles stay still; Intensity
makes them bigger; Speed sets the cycle (Very fast too); undo brings the
old setting back; unticking them all stops it.
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
    # The letters drawn one by one: how much each has grown, together.
    "ripple": f"""(function() {{ var k = {FIND}({ART}, 'rippleLetters').parent.children, g = []
        for (var i = 0; i < k.length; i++)
            if (k[i].growth !== undefined) g.push(Math.round(k[i].growth * 1000))
        return g.join(",") }})()""",
    "fade": f"{FIND}({ART}, 'textMotion').opacity",
    "glow_pulse": f"{FIND}({ART}, 'glowLoader').opacity",
    # The face's gradient: the shape (beside its Repeater) that has one.
    "gradient_shift": f"""(function() {{ var k = {FIND}({ART}, 'textFace').parent.children
        for (var i = 0; i < k.length; i++)
            if (k[i].fillGrad) return k[i].fillGrad.y1 }})()""",
    "color_cycle": f"{ART}.faceFill.toString()",
}
ORDER = list(WATCH)


def style():
    return c.scene.get(text.id).text_style


def tick(name):
    """Click an animation's checkbox in the Text tab."""
    c.item_js(f"animate:{name}", "(item.toggle(), item.toggled())")


def sample(expressions):
    c.samples = {e: [] for e in expressions}
    for t in range(0, 600, 60):
        QTimer.singleShot(t, lambda: [c.samples[e].append(c.js(e)) for e in expressions])
    # What's on screen, twice: the drawing itself has to change, not
    # only the values it's drawn from.
    c.shots = []
    for t in (150, 450):
        QTimer.singleShot(t, lambda: c.shots.append(text_on_screen()))


def varied(values):
    return len({round(v, 3) if isinstance(v, float) else v for v in values})


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
    """Only `name` ticked (the one before unticked)."""
    if getattr(c, "current", None):
        tick(c.current)
    tick(name)
    c.current = name
    sample([WATCH[name]])


def checker(name, following):
    def step():
        values = c.samples[WATCH[name]]
        c.check(f"{name}: ticked in the Text tab, it changes the canvas text over time",
                style()["animations"] == [name] and varied(values) >= 3,
                f"{style()['animations']}: {values}")
        c.check("...and it's redrawn", len(c.shots) == 2 and c.shots[0] != c.shots[1])
        c.shots[-1].save(str(OUT / f"text-{name}.png"))
        following()
    return step


def after_wiggle():
    tile = c.item_js("presetSunset", "item.children[0].running")
    c.check("...the preset tiles stay still", tile is False, str(tile))
    start("pulse")


def step_after_all():
    # Wiggle and Fade together (Color cycle still ticked).
    tick("wiggle")
    tick("fade")
    sample([WATCH["wiggle"], WATCH["fade"]])


def step_stacked():
    c.check("several at once: Wiggle and Fade run together (with Color cycle)",
            style()["animations"] == ["wiggle", "fade", "color_cycle"]
            and varied(c.samples[WATCH["wiggle"]]) >= 3 and varied(c.samples[WATCH["fade"]]) >= 3,
            str(style()["animations"]))
    c.item_js("intensitySlider", "(item.value = 2, item.moved())")
    sample([WATCH["wiggle"]])


def step_intensity():
    turn = max(abs(v) for v in c.samples[WATCH["wiggle"]])
    c.check("Intensity 2x: Wiggle turns further (beyond its usual 4°)",
            style()["animation_intensity"] == 2 and turn > 4.5, f"{turn:.1f}°")
    c.item_js("animationSpeedBox", "item.activated(3)")
    c.check("Speed: Very fast makes a cycle 0.75 s",
            style()["animation_speed"] == "very_fast" and c.js(f"{ART}.cycleMs") == 750)
    c.sm.undo()
    c.check("undo brings back Normal, in the Text tab too",
            style()["animation_speed"] == "normal"
            and c.item_js("animationSpeedBox", "item.currentText") == "Normal")
    for name in ("wiggle", "fade", "color_cycle"):
        tick(name)
    c.check("all unticked: the text stops, back to still",
            style()["animations"] == [] and c.js(f"{ART}.running") is False
            and c.js(f"{ART}.phase") == 0 and c.js(WATCH["wiggle"]) == 0
            and c.js(WATCH["fade"]) == 1)
    c.finish()


steps = [(1500, step_open), (400, step_still)]
for i, name in enumerate(ORDER):
    following = (after_wiggle if name == "wiggle"
                 else (lambda n=ORDER[i + 1]: start(n)) if i + 1 < len(ORDER)
                 else step_after_all)
    steps.append((800, checker(name, following)))
steps += [(800, step_stacked), (800, step_intensity)]
c.run(scene, steps)
