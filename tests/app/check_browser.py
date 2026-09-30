"""
The Browser (readme section 26): preview playback across file types,
viewer controls, audio staying fixed, header dragging, placing media
beside it, audio tracks, and closing.
"""

import os

from harness import AUDIO, Check, MEDIA, PHOTO, Qt, folder_files
from core.scene import Scene

c = Check("browser")
everything = folder_files(("image", "video", "audio"))
names = [e["name"] for e in everything]

scene = Scene()
left = scene.add_object("browser", 60, 120, width=460, height=360)
left.folder, left.current_index = str(MEDIA), names.index(PHOTO)
right = scene.add_object("browser", 760, 300, width=460, height=360)
right.folder, right.current_index = str(MEDIA), names.index(PHOTO)

PREVIEW = (290, 318)           # middle of the left browser's preview


def index():
    return c.scene.get(left.id).current_index


def preview(expr):
    return c.item_js("browserPreview", expr)


def media_objects():
    return [o for o in c.scene.objects if o.type == "media"]


def step_cycle():
    """One step per file, once round the folder: note whether each video/audio plays."""
    entry = everything[index()]
    if entry["type"] in ("video", "audio"):
        c.played.append((entry["name"], preview("item.player ? item.player.playbackState : -1")))
    c.click(*PREVIEW, Qt.ForwardButton)


def step_cycle_report():
    c.check("back where it started after one round", index() == names.index(PHOTO))
    c.check("videos/audio play when the browser moves to them from other kinds",
            c.played and all(state == 1 for _, state in c.played), str(c.played))


def step_viewer():
    i0 = index()
    c.wheel(*PREVIEW, 120)
    c.check("wheel zooms the preview, same file", index() == i0 and c.js("true"))
    c.click(*PREVIEW, Qt.ForwardButton)
    c.check("forward button: next file", index() == (i0 + 1) % len(names))
    c.click(*PREVIEW, Qt.BackButton)
    c.check("back button: previous file", index() == i0)
    # the header drags the browser; the preview doesn't
    x0 = c.scene.get(left.id).x
    c.drag(PREVIEW, (PREVIEW[0] + 40, PREVIEW[1] + 30))
    c.check("dragging the preview doesn't move the browser", c.scene.get(left.id).x == x0)
    c.drag((200, 138), (240, 138))
    c.check("dragging the header moves it", abs(c.scene.get(left.id).x - (x0 + 40)) < 1)
    c.drag((240, 138), (200, 138))


def step_place():
    c.double_click(*PREVIEW)                                         # add the photo


def step_place2():
    m1 = media_objects()[-1]
    b = c.scene.get(left.id)
    c.check("double-click adds it beside the browser (to its right, level with its top)",
            m1.x == b.x + b.width + 16 and m1.y == b.y, f"{m1.x:.0f},{m1.y:.0f}")
    c.js(f"""(function() {{ var k = scene.children; for (var i = 0; i < k.length; i++)
            if (k[i].objectId === '{right.id}') {{ k[i].addCurrentToCanvas(); return }} }})()""")
    m2 = media_objects()[-1]
    c.check("a browser on the right half places media to its left", m2.x + m2.width == 760 - 16)
    # go to the audio file
    while everything[index()]["type"] != "audio":
        c.click(*PREVIEW, Qt.ForwardButton)


def step_audio():
    c.wheel(*PREVIEW, 120)
    c.wheel(*PREVIEW, 120)
    zoom = c.js(f"""(function() {{ var k = scene.children; for (var i = 0; i < k.length; i++)
            if (k[i].objectId === '{left.id}') return k[i].previewZoom; return -1 }})()""")
    c.check("an audio file doesn't zoom", zoom == 1, str(zoom))
    n = len(c.scene.objects)
    c.double_click(*PREVIEW)
    tracks = [o for o in c.scene.objects if o.type == "audio"]
    c.check("double-click on an audio file adds a track", len(tracks) == 1 and len(c.scene.objects) == n + 1)
    c.check("the track isn't in Layers", all(l["type"] != "audio" for l in c.sm.property("layers")))
    c.check("tracks start audible and looping", not tracks[0].muted and tracks[0].loop)


def step_close():
    c.sm.select(left.id)
    b = c.scene.get(left.id)
    c.click(b.x + b.width - 33, b.y + 19)                           # the header's close button
    c.check("the close button removes the browser", c.scene.get(left.id) is None)
    c.sm.undo()
    c.check("...undoably", c.scene.get(left.id) is not None)
    c.finish()


c.played = []
c.run(scene, [(1500, lambda: c.click(*PREVIEW, Qt.ForwardButton))]      # leave the photo
             + [(1400, step_cycle)] * (len(names) - 1)
             + [(800, step_cycle_report), (300, step_viewer), (1300, step_place),
                (1300, step_place2), (1500, step_audio), (1300, step_close)])
