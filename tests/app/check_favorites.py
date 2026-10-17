"""
Favorites and Show New Files First (browsing containers, readme section
6.4): the star marks the file shown, Show Favorites Only lists just the
marked files, and with Show New Files First a file added to the folder
is shown at the next step, after which stepping goes on from where it
was. Works on copies in a scratch folder, so tests/media is untouched.
"""

import os
import shutil
import time

from harness import Check, GIF, OUT, PHOTO, SCREENSHOT, media
from core.scene import Scene

c = Check("favorites")

folder = OUT / "favorites-folder"
shutil.rmtree(folder, ignore_errors=True)
folder.mkdir(parents=True)
for i, name in enumerate((PHOTO, SCREENSHOT, GIF)):
    target = folder / f"{i + 1}{os.path.splitext(name)[1]}"
    shutil.copy(media(name), target)
    os.utime(target, (time.time() - 3600, time.time() - 3600))   # all old

scene = Scene()
box = scene.add_object("container", 100, 100, width=500, height=360)
box.browse_mode, box.browse_folder = True, str(folder)          # empty: shows the first file


def shown():
    item = c.scene.content_of(box.id)
    return os.path.basename(c.scene.sources[item.source_id].path) if item else None


def item(expr):
    return c.js(f"window.objectItem('{box.id}').{expr}")


def step_start():
    c.check("the browsing container starts on the folder's first file", shown() == "1.jpg", str(shown()))
    c.sm.select(box.id)


def step_star():
    x, y, _, _ = c.center_of("favoriteStar")
    c.click(x, y)
    c.check("the star marks the file shown as a favorite",
            [os.path.basename(p) for p in c.scene.get(box.id).favorites] == ["1.jpg"]
            and item("isFavorite") is True)
    c.grab("favorite-star.png")
    item("browseStep(1)")
    c.check("...another file isn't", shown() == "2.png" and item("isFavorite") is False)
    c.sm.setMediaFilter(box.id, "favorites")


def step_favorites_only():
    c.check("Show Favorites Only lists just the favorites, and moves to one",
            item("browseFiles.length") == 1 and shown() == "1.jpg", f"{item('browseFiles.length')}, {shown()}")
    c.sm.setMediaFilter(box.id, "all")
    c.sm.setNewFirst(box.id, True)


def step_new_first():
    item("browseStep(1)")
    c.check("Show New Files First: with nothing new, stepping is as usual", shown() == "2.png", str(shown()))
    shutil.copy(media(SCREENSHOT), folder / "9-new.png")             # e.g. a download


def step_new_file():
    item("lastLook = 0")                                            # don't wait out the 1 s
    item("browseStep(1)")
    c.check("a file added to the folder is shown at the next step", shown() == "9-new.png", str(shown()))
    item("browseStep(1)")
    c.check("...then stepping goes on from the file shown before it", shown() == "3.gif", str(shown()))
    c.finish()


c.run(scene, [(1500, step_start), (500, step_star), (600, step_favorites_only), (600, step_new_first),
              (600, step_new_file)])
