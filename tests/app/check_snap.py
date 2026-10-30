"""
Snapping (core/snap.py, readme section 25): moving and resizing
containers, media, and text snap to the wall's edges and each other,
with guide lines while snapped; Ctrl or the setting turns it off.
"""

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from harness import Check, Qt
from core.scene import Scene

c = Check("snap")

scene = Scene()
a = scene.add_object("container", 100, 150, width=300, height=200)
b = scene.add_object("container", 600, 150, width=300, height=200)
t = scene.add_object("container", 300, 500, width=200, height=120)


def obj(o):
    return c.scene.get(o.id)


def step_move():
    # Middle-drag moves a container from anywhere. B's left edge to 5 px
    # right of A's right edge (400); checked mid-drag, so done by hand.
    QTest.mousePress(c.win, Qt.MiddleButton, Qt.NoModifier, QPoint(750, 250))
    for i in range(1, 9):
        QTest.mouseMove(c.win, QPoint(round(750 - 195 * i / 8), 250))
    guides = c.js("scene.snapGuides") or []
    c.check("guide lines show while snapped", len(guides) >= 1, str(guides))
    QTest.mouseRelease(c.win, Qt.MiddleButton, Qt.NoModifier, QPoint(555, 250))


def step_move2():
    c.check("a moved container's edge snaps to its neighbour's (405 -> 400)",
            abs(obj(b).x - 400) < 0.01, f"x={obj(b).x}")
    c.check("...lined up at the top too, and the guides are gone after release",
            abs(obj(b).y - 150) < 0.01 and not c.js("scene.snapGuides"))
    p = c.js(f"scene.snapMove('{b.id}', 405, 150, 300, 200, 0, Qt.ControlModifier)")
    c.check("holding Ctrl: no snapping", abs(p.x() - 405) < 0.01, str(p))
    c.js("appSettings.snapping = false")
    p = c.js(f"scene.snapMove('{b.id}', 405, 150, 300, 200, 0, 0)")
    c.check("snapping off in Settings: none", abs(p.x() - 405) < 0.01)
    c.js("appSettings.snapping = true")
    # The wall's (screen's) left edge: T dragged to x = 4.
    c.drag((400, 560), (104, 560), button=Qt.MiddleButton)


def step_wall():
    c.check("the wall's left edge (4 -> 0)", abs(obj(t).x) < 0.01, f"x={obj(t).x}")
    c.sm.select(a.id)


def step_resize():
    # A's right edge bar (x 400): pulled to 380 and back to 396, which
    # snaps to B's left edge at 400.
    c.drag((400, 250), (380, 250), steps=4)
    c.drag((380, 250), (396, 250), steps=4)


def step_resize2():
    c.check("a resized edge snaps to a neighbour's edge (396 -> 400)",
            abs(obj(a).x + obj(a).width - 400) < 0.01, f"right={obj(a).x + obj(a).width}")
    c.check("...and only that edge moved", abs(obj(a).x - 100) < 0.01)
    c.finish()


c.run(scene, [(1500, step_move), (500, step_move2), (800, step_wall), (500, step_resize),
              (800, step_resize2)])
