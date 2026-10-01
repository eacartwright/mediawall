"""
Commands and shortcuts (qml/AppActions.qml, readme section 25), and the
Settings dialog (zoom step, saved between runs).
"""

from harness import Check, Qt
from bridge import project_controller as controller
from bridge.app_settings import AppSettings
from core.scene import Scene

c = Check("commands")

warnings = []
controller.QMessageBox.warning = staticmethod(lambda parent, title, text: warnings.append(text))

scene = Scene()
a = scene.add_object("container", 60, 80)
b = scene.add_object("container", 300, 200)


def step_actions():
    c.check("nothing selected: Duplicate, Delete, arrange are off",
            not c.js("appActions.duplicate.enabled") and not c.js("appActions.deleteSelected.enabled")
            and not c.js("appActions.bringToFront.enabled"))
    c.sm.select(a.id)
    c.check("the bottom object: Bring to Front on, Send to Back off",
            c.js("appActions.bringToFront.enabled") and not c.js("appActions.sendToBack.enabled"))
    n = len(c.scene.objects)
    c.key(Qt.Key_D, Qt.ControlModifier)
    c.check("Ctrl+D duplicates", len(c.scene.objects) == n + 1)
    c.key(Qt.Key_Z, Qt.ControlModifier)
    c.check("Ctrl+Z undoes", len(c.scene.objects) == n)
    c.key(Qt.Key_Y, Qt.ControlModifier)
    c.check("Ctrl+Y redoes", len(c.scene.objects) == n + 1)
    c.key(Qt.Key_Z, Qt.ControlModifier)
    c.key(Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
    c.check("Ctrl+Shift+Z redoes too", len(c.scene.objects) == n + 1)
    c.sm.select(a.id)
    c.key(Qt.Key_Up, Qt.ControlModifier | Qt.ShiftModifier)
    c.check("Ctrl+Shift+Up brings it to the front", c.scene.layer_order()[0].id == a.id)
    c.win.setProperty("presenting", True)


def step_present():
    c.check("Present: editing commands are off",
            not c.js("appActions.undo.enabled") and not c.js("appActions.addContainer.enabled"))
    c.key(Qt.Key_F5)


def step_settings():
    c.check("F5 toggles Present off", not c.win.property("presenting"))
    c.check("zoom step defaults to 10%", c.js("appSettings.zoomStep") == 10.0)
    c.js("settingsDialog.open()")
    c.js("appSettings.zoomStep = 25")


def step_settings2():
    c.check("the dialog shows the new value", c.item_js("zoomStepBox", "item.value") == 25)
    c.grab("settings.png")
    c.js("settingsDialog.close()")
    c.check("a new settings object (a restart) reads it back", AppSettings().zoomStep == 25.0)
    c.js("appSettings.resetZoomStep()")
    c.check("Default restores 10%", c.js("appSettings.zoomStep") == 10.0)
    c.finish()


def step_recent():
    recent = c.js("appSettings.recentProjects")
    c.check("the opened project is first in Open Recent",
            bool(recent) and recent[0].endswith("commands.mediawall"), str(recent))
    x, y, _, _ = c.center_of("recentButton")
    c.click(x, y)
    c.check("the ▾ beside Open shows the recent list", c.js("recentMenu.visible") and c.js("recentMenu.count") >= 3)
    c.js("recentMenu.close()")
    gone = "/no/such/folder/gone.mediawall"
    c.js(f"appSettings.addRecentProject('{gone}')")
    c.js(f"projectController.openRecent('{gone}')")
    c.check("a missing recent project: a warning, and it leaves the list",
            len(warnings) == 1 and gone not in c.js("appSettings.recentProjects"))


c.run(scene, [(1500, step_actions), (1000, step_present), (1000, step_recent), (1000, step_settings),
              (800, step_settings2)])
