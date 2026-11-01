"""
A browser's Add File… (readme section 26): files chosen one by one, with
no folder browsed. Pictures and videos go on the canvas beside the
browser, audio becomes Playback tracks; all of one choice is one undo
step. (The file dialog itself can't be driven here: the check calls
what its button calls with the chosen files.)
"""

import json

from harness import AUDIO, PHOTO, VIDEO, Check, media
from core.scene import Scene

c = Check("add_file")

scene = Scene()
browser = scene.add_object("browser", 100, 120, width=520, height=420)


def media_objects():
    return [o for o in c.scene.objects if o.type == "media" and o.parent_id is None]


def tracks():
    return [o for o in c.scene.objects if o.type == "audio"]


def step_add():
    c.check("the browser has an Add File button", c.center_of("addFileButton") is not None)
    c.grab("add-file.png")
    files = [{"path": media(PHOTO), "type": "image"}, {"path": media(VIDEO), "type": "video"},
             {"path": media(AUDIO), "type": "audio"}]
    c.js(f"window.objectItem('{browser.id}').addFiles({json.dumps(files)})")


def step_added():
    added = media_objects()
    c.check("pictures and videos go on the canvas", len(added) == 2, str(len(added)))
    c.check("...beside the browser (to its right)", all(o.x >= 100 + 520 for o in added),
            str([round(o.x) for o in added]))
    c.check("audio becomes a track", len(tracks()) == 1)
    c.sm.undo()


def step_undone():
    c.check("one undo removes the whole choice", not media_objects() and not tracks())
    c.finish()


c.run(scene, [(1500, step_add), (600, step_added), (400, step_undone)])
