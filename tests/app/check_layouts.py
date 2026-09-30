"""
Layouts (readme section 17): Save Layout, Add Layout to Wall, New from
Layout, and opening a layout as a project. File dialogs and message
boxes are answered by stand-ins.
"""

import json
import os

from harness import OUT, Check, MEDIA, PHOTO, media
import bridge.project_controller as controller
from core.scene import Scene

c = Check("layouts")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
left = scene.add_object("container", 20, 60, width=600, height=660)
right = scene.add_object("container", 640, 60, width=600, height=660)
scene.add_media_to_container(photo.id, left.id)
scene.add_media_to_container(photo.id, right.id)
scene.add_media(photo.id, 900, 500)
browser = scene.add_object("browser", 300, 300)
browser.folder = str(MEDIA)

# Stand-ins for dialogs.
answers = {}
controller.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (answers["save"], ""))
controller.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (answers["open"], ""))
messages = []
controller.QMessageBox.critical = staticmethod(lambda parent, title, text: messages.append(text))

LAYOUT = str(OUT / "halves.mediawall.layout")


def kinds():
    return sorted(o.type for o in c.scene.objects)


def step_save():
    before = kinds()
    answers["save"] = str(OUT / "halves.layout")                   # a partial extension, as typed
    c.pc.saveLayout()
    ok = os.path.exists(LAYOUT)
    data = json.load(open(LAYOUT, encoding="utf-8")) if ok else {"objects": []}
    c.check("Save Layout writes <name>.mediawall.layout", ok)
    c.check("...with only the containers", [o["type"] for o in data["objects"]] == ["container", "container"])
    c.check("the wall is unchanged", kinds() == before)


def step_add():
    n = len(c.scene.objects)
    answers["open"] = LAYOUT
    c.pc.addLayoutToWall()
    c.check("Add Layout to Wall adds its containers", len(c.scene.objects) - n == 2)
    c.sm.undo()
    c.check("...as one undo step", len(c.scene.objects) == n)


def step_new():
    c.pc._set_dirty(False)
    c.pc.newFromLayout()
    c.check("New from Layout: a wall of empty containers",
            kinds() == ["container", "container"]
            and all(c.scene.content_of(o.id) is None for o in c.scene.objects))
    c.check("...untitled and unmodified",
            c.pc.property("title").startswith("Untitled") and not c.pc.property("dirty"))
    c.pc.openPath(LAYOUT)
    c.check("opening a layout as a project says what it is",
            any("layout, not a project" in m for m in messages))
    c.finish()


c.run(scene, [(1500, step_save), (1000, step_add), (1000, step_new)])
