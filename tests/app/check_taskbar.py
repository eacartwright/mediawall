"""
Full Screen keeping the taskbar (Settings → General; readme section 15):
with the setting on, Full Screen is a maximized window with the toolbar
hidden, Present still fills the whole screen, and stepping out goes back
the same way, to the window as it was.
"""

from PySide6.QtGui import QWindow

from harness import Check, Qt
from core.scene import Scene

c = Check("taskbar")

scene = Scene()
scene.add_object("container", 300, 200)


def state():
    return c.win.visibility()


def toolbar_shown():
    return c.js("toolbar.visible")


def step_start():
    c.start = state()
    c.js("appSettings.keepTaskbar = true")
    c.key(Qt.Key_F11)


def step_full_screen():
    c.check("with the setting, Full Screen is a maximized window (taskbar showing)",
            c.win.property("fullScreenEditing") and state() == QWindow.Maximized, str(state()))
    c.check("...without the toolbar", toolbar_shown() is False)
    c.key(Qt.Key_F5)


def step_present():
    c.check("Present still fills the whole screen", state() == QWindow.FullScreen, str(state()))
    c.key(Qt.Key_Escape)


def step_back_to_full_screen():
    c.check("leaving Present goes back to the maximized Full Screen",
            c.win.property("fullScreenEditing") and not c.win.property("presenting")
            and state() == QWindow.Maximized, str(state()))
    c.key(Qt.Key_Escape)


def step_window():
    c.check("leaving Full Screen gives back the window as it was, with the toolbar",
            not c.win.property("fullScreenEditing") and state() == c.start
            and toolbar_shown() is True, f"{state()} vs {c.start}")
    c.js("appSettings.keepTaskbar = false")
    c.key(Qt.Key_F11)


def step_plain_full_screen():
    c.check("with the setting off, Full Screen covers the whole screen again",
            state() == QWindow.FullScreen, str(state()))
    c.key(Qt.Key_Escape)
    c.finish()


c.run(scene, [(1500, step_start), (800, step_full_screen), (800, step_present),
              (800, step_back_to_full_screen), (800, step_window), (800, step_plain_full_screen)])
