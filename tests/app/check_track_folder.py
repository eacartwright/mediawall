"""
Audio tracks through a folder, and the pause at the end (readme section
14.5): ◀ ▶ step to the previous/next audio file in the track's folder
(by name; not undone, as with browsing), Continue Play goes on to the
next file at the end of one (and greys out Loop), and with a pause set
a looping track waits that long before starting over. Works on copies
in a scratch folder, so tests/media is untouched.
"""

import os
import shutil

from harness import AUDIO, MP3, OUT, Check, media
from core.scene import Scene

c = Check("track_folder")

folder = OUT / "track-folder"
shutil.rmtree(folder, ignore_errors=True)
folder.mkdir(parents=True)
for name, original in (("1.m4a", AUDIO), ("2.mp3", MP3), ("3.m4a", AUDIO)):
    shutil.copy(media(original), folder / name)
(folder / "photo.jpg").write_bytes(b"")          # not audio: skipped

scene = Scene()
source = scene.add_source(str(folder / "1.m4a"), "audio")
track = scene.add_audio_track(source.id)


def get():
    return c.scene.get(track.id)


def playing_file():
    return os.path.basename(c.scene.sources[get().source_id].path)


def view(expr):
    return c.js(f"scene.viewFor('{track.id}') ? scene.viewFor('{track.id}').{expr} : null")


def near_end():
    view(f"seek(scene.viewFor('{track.id}').duration - 300)")


def step_open():
    c.open_sidebar()


def step_tab():
    c.choose_tab("playbackTab")


def step_next():
    x, y, _, _ = c.center_of("trackNext")
    c.click(x, y)


def step_stepped():
    c.check("▶ goes to the next audio file in the folder", playing_file() == "2.mp3", playing_file())
    c.sm.setVolume(track.id, 0.5)                # an undoable change after it
    c.sm.undo()


def step_undone():
    c.check("undo doesn't change the file (stepping isn't undone)",
            playing_file() == "2.mp3" and get().volume == 1.0, f"{playing_file()}, {get().volume}")
    x, y, _, _ = c.center_of("trackPrev")
    c.click(x, y)
    c.click(x, y)


def step_wrapped():
    c.check("◀ goes back, round to the last file", playing_file() == "3.m4a", playing_file())
    x, y, _, _ = c.center_of("trackContinuePlay")
    c.click(x, y)


def step_continue_on():
    c.check("Continue Play turns on for the track", get().continue_play is True)
    c.check("...and the player doesn't loop by itself", view("loop") is False)
    near_end()


def step_continued():
    c.check("at the end of a file, Continue Play goes on to the next (round to the first)",
            playing_file() == "1.m4a", playing_file())
    c.sm.setContinuePlay(track.id, False)
    c.sm.setLoopGap(track.id, 1.5)


def step_gap_set():
    c.grab("track-card.png")
    c.check("a pause is set (and Loop is left to the track)",
            get().loop_gap == 1.5 and view("loop") is False, str(get().loop_gap))
    near_end()


def step_in_gap():
    c.check("at the end, with a pause, the track waits", view("ended") is True
            and c.item_js("trackGapTimer", "item.running") in (True, None), str(view("ended")))


def step_after_gap():
    c.check("...then starts over", view("ended") is False and view("position") < 5000
            and playing_file() == "1.m4a", f"{view('ended')}, {view('position')}")
    c.finish()


c.run(scene, [(2000, step_open), (500, step_tab), (500, step_next), (1200, step_stepped),
              (500, step_undone), (1500, step_wrapped), (500, step_continue_on),
              (2500, step_continued), (1000, step_gap_set), (1000, step_in_gap),
              (2500, step_after_gap)])
