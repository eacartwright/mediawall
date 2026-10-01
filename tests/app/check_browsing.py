"""
Browsing containers (readme section 6.4): viewer-style controls, file
stepping, autoplay, empty containers, undo, and Present.
"""

import os

import shutil

from harness import (Check, GIF, MEDIA, OUT, PHOTO, Qt, folder_files, media)
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
    c.start_name = f0
    c.wheel(360, 290, 120)
    c.check("wheel zooms the picture, same file", shown() == f0 and abs(content().width / w0 - (1 + step)) < 1e-3)
    i0 = names.index(shown())
    c.click(360, 290, Qt.ForwardButton)
    c.check("forward button: next file", shown() == names[(i0 + 1) % len(names)], shown())
    c.click(360, 290, Qt.BackButton)
    c.check("back button: previous file", shown() == names[i0], shown())
    audio = [e["name"] for e in folder_files(("audio",))]
    c.check("audio files are skipped", audio and not set(audio) & set(names), str(audio))
    c.wheel(360, 290, 0, dx=-120)
    c.check("tilting the wheel right: next file", shown() == names[(i0 + 1) % len(names)], shown())
    c.wheel(360, 290, 0, dx=120)
    c.check("tilting it left: previous file", shown() == names[i0], shown())
    c.sm.select(box.id)
    c.key(Qt.Key_Right)
    c.check("Right arrow (selected): next file", shown() == names[(i0 + 1) % len(names)], shown())
    c.key(Qt.Key_Left)
    c.check("Left arrow: previous file", shown() == names[i0], shown())
    c.press(360, 290, Qt.ForwardButton)                             # held until step_hold


def step_hold():
    c.release(360, 290, Qt.ForwardButton)
    i0 = names.index(c.start_name)
    moved = (names.index(shown()) - i0) % len(names)
    c.check("holding the forward button keeps stepping", 2 <= moved < len(names) - 1, f"{moved} steps")
    for _ in range(moved):                                          # back to where it was
        c.key(Qt.Key_Left)
    c.check("...and it stops when released", shown() == c.start_name, shown())


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
    folder_answer[0] = str(OTHER)
    c.sm.chooseBrowseFolder(box.id)                                 # Browse Folder… on a filled container


def step_other_folder():
    b = c.scene.get(box.id)
    c.check("Browse Folder… on a filled container browses the chosen folder",
            b.browse_mode and os.path.normcase(b.browse_folder) == os.path.normcase(str(OTHER)))
    c.check("...and moves to its first file", shown() == GIF, str(shown()))
    folder_answer[0] = str(MEDIA)
    c.sm.chooseBrowseFolder(box.id)


def step_other_folder2():
    c.check("choosing another folder again: its first file", shown() == names[0], str(shown()))
    c.js(f"""(function() {{ var k = scene.children; for (var i = 0; i < k.length; i++)
            if (k[i].objectId === '{box.id}') objectMenu.openFor(k[i]) }})()""")
    triggered = c.js("""(function() { for (var i = 0; i < objectMenu.count; i++) {
        var it = objectMenu.itemAt(i)
        if (it && it.text === 'Show Videos Only' && it.visible) { it.triggered(); return true } }
        return false })()""")
    c.js("objectMenu.close()")
    c.check("a browsing container's menu offers Show Videos Only", triggered is True)


def step_filter():
    videos = [e["name"] for e in folder_files(("video",))]
    c.check("...which moves to a video and steps through videos only",
            shown() in videos and c.scene.get(box.id).media_filter == "video", str(shown()))
    c.click(360, 290, Qt.ForwardButton)
    c.check("...(forward: another video)", shown() in videos, str(shown()))
    c.sm.setMediaFilter(box.id, "audio")
    c.check("a container can't be set to audio", c.scene.get(box.id).media_filter == "video")
    c.finish()


# The folder dialog for the empty container: answer with tests/media.
import bridge.scene_model as scene_model                            # noqa: E402
folder_answer = [str(MEDIA)]
scene_model.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder_answer[0])

# A second folder to browse, holding one file.
OTHER = OUT / "other folder"
OTHER.mkdir(parents=True, exist_ok=True)
shutil.copy(media(GIF), OTHER / GIF)

c.run(scene, [(1500, step_controls), (800, step_hold), (1300, step_pan_and_move), (1300, step_undo_and_reset),
              (1300, step_after_reset), (1800, step_autoplay), (1500, step_autoplay2),
              (1800, step_autoplay3), (1500, step_empty), (1500, step_present),
              (1300, step_present2), (1300, step_end), (1300, step_other_folder),
              (1300, step_other_folder2), (1300, step_filter)])
