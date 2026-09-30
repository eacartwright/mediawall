"""
Browsing containers (readme section 6.4): viewer-style controls, file
stepping, autoplay, empty containers, undo, and Present.
"""

import os

from harness import (Check, MEDIA, PHOTO, Qt, folder_files, media)
from core.scene import FIT_CONTAIN, Scene

c = Check("browsing")
names = [e["name"] for e in folder_files()]

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
# The second container starts on an image that the folder order follows
# with a video, to check that stepping image -> video plays.
_files = folder_files()
_start = next(e for i, e in enumerate(_files)
              if e["type"] == "image" and _files[(i + 1) % len(_files)]["type"] == "video")
shot = scene.add_source(_start["path"], "image", 0, 0)
box = scene.add_object("container", 60, 80, width=600, height=420)
scene.add_media_to_container(photo.id, box.id)
box.browse_mode, box.browse_folder = True, str(MEDIA)
second = scene.add_object("container", 700, 80, width=500, height=420)      # stepped to a video next
scene.add_media_to_container(shot.id, second.id)
empty = scene.add_object("container", 60, 540, width=300, height=200)     # double-click: browse


def content(cid=box.id):
    return c.scene.content_of(cid)


def shown(cid=box.id):
    item = content(cid)
    return os.path.basename(c.scene.sources[item.source_id].path) if item else None


def geo(o):
    return (round(o.x, 1), round(o.y, 1), round(o.width, 1), round(o.height, 1))


def player_state(cid):
    item = content(cid)
    return c.js(f"scene.viewFor('{item.id}') && scene.viewFor('{item.id}').player "
                f"? scene.viewFor('{item.id}').player.playbackState : -1")


def step_controls():
    c.sm.startBrowsing(second.id)
    step = c.js("appSettings.zoomStep") / 100
    f0, w0 = shown(), content().width
    c.wheel(360, 290, 120)
    c.check("wheel zooms the picture, same file", shown() == f0 and abs(content().width / w0 - (1 + step)) < 1e-3)
    i0 = names.index(shown())
    c.click(360, 290, Qt.ForwardButton)
    c.check("forward button: next file", shown() == names[(i0 + 1) % len(names)], shown())
    c.click(360, 290, Qt.BackButton)
    c.check("back button: previous file", shown() == names[i0], shown())
    audio = [e["name"] for e in folder_files(("audio",))]
    c.check("audio files are skipped", audio and not set(audio) & set(names), str(audio))


def step_pan_and_move():
    b0, c0 = geo(c.scene.get(box.id)), geo(content())
    c.drag((360, 290), (420, 330))
    c.check("left-drag pans the picture, container stays",
            geo(c.scene.get(box.id)) == b0 and (round(content().x - c0[0]), round(content().y - c0[1])) == (60, 40))
    c.drag((200, 84), (240, 104))                                   # border strip, away from handles
    b = c.scene.get(box.id)
    c.check("dragging the border strip moves the container", (b.x, b.y) == (100, 100), f"{b.x},{b.y}")
    c.drag((420, 320), (380, 300), Qt.MiddleButton)
    b = c.scene.get(box.id)
    c.check("middle-drag moves the container", (b.x, b.y) == (60, 80), f"{b.x},{b.y}")


def step_undo_and_reset():
    before = geo(content())
    c.sm.undo()                                                     # the middle-drag move
    b = c.scene.get(box.id)
    c.check("undo moves the container, keeps pan/zoom", (b.x, b.y) == (100, 100) and geo(content()) == before)
    c.double_click(400, 310)


def step_after_reset():
    item, b = content(), c.scene.get(box.id)
    fitted = abs(item.height - b.height) < 0.5 or abs(item.width - b.width) < 0.5
    c.check("double-click resets the zoom", fitted and item.x <= 0.5 and item.y <= 0.5)
    c.sm.fitContent(box.id, False)                                  # Fit
    c.click(360, 290, Qt.ForwardButton)
    b, item = c.scene.get(box.id), content()
    c.check("Fit is remembered for the next file",
            b.fit_mode == FIT_CONTAIN and item.width <= b.width + 0.5 and item.height <= b.height + 0.5)
    c.click(950, 290, Qt.ForwardButton)                             # second: image -> video


def step_autoplay():
    c.check("image -> video: plays", player_state(second.id) == 1, f"{shown(second.id)}")
    c.sm.setPlaying(content(second.id).id, False)                   # pause it
    c.click(950, 290, Qt.ForwardButton)                             # -> first file (a GIF)


def step_autoplay2():
    c.check("after pausing a video, the next file plays", content(second.id).playing, shown(second.id))
    # Step on to the next video (however far, in the folder's order).
    here = names.index(shown(second.id))
    kinds = [e["type"] for e in folder_files()]
    ahead = next(k for k in range(1, len(names) + 1) if kinds[(here + k) % len(names)] == "video")
    c.from_kind = kinds[here]
    for _ in range(ahead):
        c.click(950, 290, Qt.ForwardButton)


def step_autoplay3():
    c.check(f"{c.from_kind} -> ... -> video: plays", player_state(second.id) == 1, shown(second.id))
    c.double_click(210, 640)                                        # empty container


def step_empty():
    e = c.scene.get(empty.id)
    c.check("double-click on an empty container starts browsing (folder dialog)",
            e.browse_mode and os.path.normcase(e.browse_folder) == os.path.normcase(str(MEDIA)))
    c.check("...and shows the first file straight away", shown(empty.id) == names[0], str(shown(empty.id)))
    c.win.setProperty("presenting", True)


def step_present():
    b0, f0, w0 = geo(c.scene.get(box.id)), shown(), content().width
    c.wheel(400, 300, 120)
    c.click(400, 300, Qt.ForwardButton)
    c.drag((400, 300), (440, 320))
    c.drag((400, 104), (440, 140))                                  # border strip: no moving in Present
    c.check("Present: zoom, forward, and pan still work", shown() != f0 or content().width != w0)
    c.check("Present: the container never moves", geo(c.scene.get(box.id)) == b0)
    c.double_click(400, 300)


def step_present2():
    c.check("Present: double-click resets zoom, doesn't exit", c.win.property("presenting") is True)
    c.key(Qt.Key_Escape)


def step_end():
    c.check("Esc leaves Present", not c.win.property("presenting"))
    c.sm.stopBrowsing(box.id)
    c.sm.select("")
    before = shown()
    c.click(360, 290, Qt.ForwardButton)
    c.check("after Stop Browsing, forward does nothing", shown() == before)
    c.finish()


# The folder dialog for the empty container: answer with tests/media.
import bridge.scene_model as scene_model                            # noqa: E402
scene_model.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(MEDIA))

c.run(scene, [(1500, step_controls), (1300, step_pan_and_move), (1300, step_undo_and_reset),
              (1300, step_after_reset), (1800, step_autoplay), (1500, step_autoplay2),
              (1800, step_autoplay3), (1500, step_empty), (1500, step_present),
              (1300, step_present2), (1300, step_end)])
