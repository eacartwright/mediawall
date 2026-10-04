"""
Full Screen and Present (readme section 15): entering and leaving, the
view-only canvas, browsers still working, the idle pointer, and the
Present button in Full Screen.
"""

from PySide6.QtGui import QWindow

from harness import Check, MEDIA, PHOTO, Qt, folder_files, media
from core.scene import Scene

c = Check("present")
names = [e["name"] for e in folder_files(("image", "video", "audio"))]

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
picture = scene.add_media(photo.id, 100, 150)
picture.width, picture.height = 400, 225
browser = scene.add_object("browser", 700, 120, width=460, height=380)
browser.folder = str(MEDIA)
frame = scene.add_object("container", 100, 450, width=400, height=250)    # not browsing
scene.add_media_to_container(photo.id, frame.id)


def win_state():
    return c.win.visibility()


def step_enter():
    c.start_visibility = win_state()
    c.sm.select(picture.id)
    c.win.setProperty("presenting", True)


def step_present():
    c.check("Present: window is full screen", win_state() == QWindow.FullScreen)
    c.check("Present: selection cleared", c.sm.property("selectedId") == "")
    x0 = c.scene.get(picture.id).x
    c.drag((300, 260), (380, 340))
    c.check("Present: media can't be dragged or selected",
            c.scene.get(picture.id).x == x0 and c.sm.property("selectedId") == "")
    i0 = c.scene.get(browser.id).current_index
    c.click(930, 300, Qt.ForwardButton)
    c.check("Present: the browser still works", c.scene.get(browser.id).current_index == (i0 + 1) % len(names))
    f0, w0 = c.scene.get(frame.id).x, c.scene.content_of(frame.id).width
    c.wheel(300, 575, 120)
    c.drag((300, 575), (340, 600))
    c.check("Present: any container's picture still zooms (the container stays put)",
            c.scene.content_of(frame.id).width > w0 and c.scene.get(frame.id).x == f0)
    c.sm.select(browser.id)
    c.key(Qt.Key_Delete)
    c.check("Present: Delete is off", c.scene.get(browser.id) is not None)
    c.move(640, 400)


def step_idle():
    c.check("Present: the pointer hides when idle", c.win.cursor().shape() == Qt.BlankCursor)
    c.move(660, 420)


def step_idle2():
    c.check("...and comes back when it moves", c.win.cursor().shape() != Qt.BlankCursor)
    c.double_click(300, 260)                                        # on the (view-only) picture


def step_left():
    c.check("double-click on media leaves Present", not c.win.property("presenting")
            and win_state() == c.start_visibility)
    c.key(Qt.Key_F11)


def step_full_screen():
    c.check("F11: Full Screen editing", c.win.property("fullScreenEditing") and win_state() == QWindow.FullScreen)
    c.move(c.win.width() // 2, c.win.height() // 2)


def step_present_button():
    c.check("Full Screen: a Present button beside the exit button",
            c.js("presentButton.visible") and c.js("exitButton.visible")
            and c.js("saveButton.visible"))
    c.grab("full-screen-buttons.png")
    c.js("sceneModel.addContainer(900, 600)")                       # something to save
    dirty = c.js("projectController.dirty")
    c.click(c.win.width() - 12 - 40 - 8 - 40 - 8 - 20, 12 + 20)     # the Save button
    c.check("...and a Save button beside that, which saves",
            dirty and not c.js("projectController.dirty"))
    c.js("sceneModel.undo()")
    c.click(c.win.width() - 12 - 40 - 8 - 20, 12 + 20)             # the Present button


def step_present_button2():
    c.check("the Present button starts Present", c.win.property("presenting") is True)
    c.move(c.win.width() // 2 + 30, c.win.height() // 2)
    c.check("in Present only the exit button shows",
            not c.js("presentButton.visible") and not c.js("saveButton.visible"))
    c.key(Qt.Key_Escape)


def step_back():
    c.check("Esc leaves Present, back to Full Screen", not c.win.property("presenting")
            and c.win.property("fullScreenEditing"))
    c.sm.select(picture.id)
    c.key(Qt.Key_Escape)


def step_back2():
    c.check("Esc with a selection only deselects", c.win.property("fullScreenEditing")
            and c.sm.property("selectedId") == "")
    c.key(Qt.Key_Escape)


def step_end():
    c.check("Esc with nothing selected leaves Full Screen", not c.win.property("fullScreen")
            and win_state() == c.start_visibility)
    c.finish()


c.run(scene, [(1500, step_enter), (1500, step_present), (3200, step_idle), (400, step_idle2), (1200, step_left),
              (1200, step_full_screen), (1000, step_present_button), (1000, step_present_button2),
              (1000, step_back), (800, step_back2), (1000, step_end)])
