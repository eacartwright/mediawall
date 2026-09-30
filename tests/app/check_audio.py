"""
Audio (readme section 14): the Audio tab, speed/A-B loop, the speed
range setting, and video as audio.
"""

import os

from harness import Check, MEDIA, PHOTO, VIDEO, WEBM, Qt, folder_files, media
from core.scene import Scene

c = Check("audio")
names = [e["name"] for e in folder_files()]

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
video = scene.add_source(media(VIDEO), "video", 0, 0)
webm = scene.add_source(media(WEBM), "video", 0, 0)
scene.add_media(photo.id, 40, 90)
box = scene.add_object("container", 600, 90, width=320, height=200)
scene.add_media_to_container(webm.id, box.id)
clip = scene.add_media(video.id, 60, 330)            # topmost: first card in the Audio tab
clip.width, clip.height = 300, 533


def rows():
    return c.sm.property("audioItems").rowCount()


def speed():
    return c.scene.get(clip.id).speed


def slider_ends():
    x, y, w, h = c.center_of("speedSlider")
    return (x - w / 2 + 4, y), (x + w / 2 - 4, y)


def step_list():
    c.check("the Audio tab lists both videos (free and in a container)", rows() == 2, str(rows()))
    c.sm.select(clip.id)
    c.open_sidebar()


def step_tab():
    c.choose_tab("audioTab")


def step_speed():
    c.check("speed range defaults to 0.5x .. 3x", (c.js("appSettings.speedMin"), c.js("appSettings.speedMax")) == (0.5, 3.0))
    lo, hi = slider_ends()
    c.drag(hi, (hi[0] + 120, hi[1]))
    c.check("speed slider fully right = 3x", abs(speed() - 3.0) < 0.01, str(speed()))
    c.drag(lo, (lo[0] - 120, lo[1]))
    c.check("speed slider fully left = 0.5x", abs(speed() - 0.5) < 0.01, str(speed()))
    c.js("appSettings.speedMax = 2")
    lo, hi = slider_ends()
    c.drag(hi, (hi[0] + 120, hi[1]))
    c.check("with Fastest set to 2x, fully right = 2x", abs(speed() - 2.0) < 0.01, str(speed()))
    c.js("appSettings.resetSpeedRange()")


def step_loop():
    c.sm.setLoopA(clip.id, 2000)
    c.sm.setLoopB(clip.id, 6000)
    o = c.scene.get(clip.id)
    c.check("A-B loop points stored", (o.loop_a, o.loop_b) == (2000, 6000))
    c.sm.undo()
    o = c.scene.get(clip.id)
    c.check("undo reverts the last point (B)", (o.loop_a, o.loop_b) == (2000, -1))
    c.sm.setLoopB(clip.id, 3000)
    c.js(f"scene.viewFor('{clip.id}').seek(2500)")


def step_loop2():
    pos = c.js(f"scene.viewFor('{clip.id}').position")
    c.check("playback stays between A and B", 1900 <= pos <= 3100, f"{pos:.0f} ms")
    c.sm.clearLoop(clip.id)
    c.js(f"scene.viewFor('{clip.id}').player.position = 20000")


def step_convert():
    c.js(f"objectMenu.openFor(scene.viewFor('{clip.id}').parent)")
    triggered = c.js("""(function() { for (var i = 0; i < objectMenu.count; i++) {
        var it = objectMenu.itemAt(i)
        if (it && it.text === 'Convert to Audio Track' && it.visible) { it.triggered(); return true } }
        return false })()""")
    c.js("objectMenu.close()")
    c.check("the right-click menu offers Convert to Audio Track", triggered is True)
    tracks = [o for o in c.scene.objects if o.type == "audio"]
    c.check("the video leaves the canvas; an audible track of it appears",
            c.scene.get(clip.id) is None and len(tracks) == 1 and tracks[0].source_id == video.id
            and not tracks[0].muted)
    c.track = tracks[0].id if tracks else ""


def step_convert2():
    pos = c.js(f"scene.viewFor('{c.track}') ? scene.viewFor('{c.track}').position : -1")
    c.check("the track carries on from the video's position", pos is not None and 19000 <= pos <= 26000, f"{pos}")
    c.sm.undo()
    c.check("one undo brings the video back", c.scene.get(clip.id) is not None
            and not any(o.type == "audio" for o in c.scene.objects))
    c.finish()


c.run(scene, [(1500, step_list), (800, step_tab), (800, step_speed), (1000, step_loop),
              (1500, step_loop2), (1500, step_convert), (1500, step_convert2)])
