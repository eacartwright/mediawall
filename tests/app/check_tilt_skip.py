"""
Tilting the wheel over a video or audio file skips 10% of its length (readme
section 55): free, in a container, and in a browser's preview. An animated image
doesn't skip: there a tilt does what it did before, which is nothing on a free
object and the next file in a browser. Skipping stays within the file, and a
looping video goes on playing after skipping past its end.
"""

import shutil

from harness import GIF, MP3, OUT, VIDEO, Check, media
from core.scene import Scene

c = Check("tilt_skip")

scene = Scene()
video = scene.add_source(media(VIDEO), "video", 0, 0)
gif = scene.add_source(media(GIF), "image", 600, 326)

free_video = scene.add_media(video.id, 420, 80)
free_video.width, free_video.height = 200, 200
free_video.playing = False                     # so nothing but the skip moves it
free_gif = scene.add_media(gif.id, 660, 80)
free_gif.width, free_gif.height = 200, 110
box = scene.add_object("container", 420, 320, width=240, height=200)
scene.add_media_to_container(video.id, box.id)

# A browser's folder: a GIF, then audio, by name.
FOLDER = OUT / "tilt"
FOLDER.mkdir(parents=True, exist_ok=True)
shutil.copy(media(GIF), FOLDER / "a.gif")
shutil.copy(media(MP3), FOLDER / "b.mp3")
browser = scene.add_object("browser", 700, 320, width=480, height=360)
browser.folder = str(FOLDER)

VIDEO_SPOT = (520, 180)
GIF_SPOT = (760, 135)
BOX_SPOT = (540, 420)
PREVIEW_SPOT = (940, 450)
RIGHT, LEFT = -120, 120                        # a tilt right is a negative x


def view(object_id):
    return f"scene.viewFor('{object_id}')"


def where(object_id):
    return c.js(view(object_id) + ".player.position"), c.js(view(object_id) + ".duration")


def content_id():
    return c.scene.content_of(box.id).id


def step_start():
    position, duration = where(free_video.id)
    c.check("the video has loaded, paused", duration > 0 and c.scene.get(free_video.id).playing is False,
            f"{position} / {duration}")
    c.duration = duration
    c.wheel(*VIDEO_SPOT, 0, dx=RIGHT)


def step_forward():
    position, _ = where(free_video.id)
    c.check("a tilt right skips forward 10%, without selecting it",
            abs(position - c.duration * 0.1) < c.duration * 0.03 and c.sm.selectedId == "",
            f"{position} of {c.duration}")
    c.wheel(*VIDEO_SPOT, 0, dx=LEFT)


def step_back():
    position, _ = where(free_video.id)
    c.check("a tilt left skips back", position < c.duration * 0.03, f"{position} of {c.duration}")
    c.wheel(*VIDEO_SPOT, 0, dx=RIGHT)
    c.wheel(*VIDEO_SPOT, 0, dx=LEFT)
    c.wheel(*VIDEO_SPOT, 0, dx=RIGHT)
    c.js(view(free_video.id) + ".seek(0)")


def step_not_before_start():
    c.wheel(*VIDEO_SPOT, 0, dx=LEFT)


def step_at_start():
    position, _ = where(free_video.id)
    c.check("...no further than the start", position < c.duration * 0.03, str(position))
    size = c.scene.get(free_video.id).width
    c.wheel(*VIDEO_SPOT, 120)
    c.check("the plain wheel isn't a skip", where(free_video.id)[0] < c.duration * 0.03
            and c.scene.get(free_video.id).width == size)
    c.frame = c.js(view(free_gif.id) + ".animation.currentFrame")
    c.wheel(*GIF_SPOT, 0, dx=RIGHT)
    c.check("a tilt does nothing to an animated image",
            c.js(view(free_gif.id) + ".animation.currentFrame") - c.frame < 20
            and c.scene.get(free_gif.id).x == 660)
    # In a container, and playing.
    c.js(view(content_id()) + ".seek(%d)" % (c.js(view(content_id()) + ".duration") * 0.5))


def step_container():
    c.before = where(content_id())[0]
    c.wheel(*BOX_SPOT, 0, dx=RIGHT)
    c.check("in a container it skips the content",
            where(content_id())[0] > c.before, f"{c.before} -> {where(content_id())[0]}")
    c.js(view(content_id()) + ".seek(%d)" % (where(content_id())[1] * 0.98))


def step_past_end():
    c.wheel(*BOX_SPOT, 0, dx=LEFT)                 # (another direction: not a hold)
    c.wheel(*BOX_SPOT, 0, dx=RIGHT)


def step_looped():
    c.check("past the end, a looping video goes on playing",
            c.js(view(content_id()) + ".player.playbackState === 1") is True,
            str(c.js(view(content_id()) + ".player.playbackState")))
    c.check("the browser starts on the GIF", c.item_js("browserPreview", "item.name") == "a.gif",
            str(c.item_js("browserPreview", "item.name")))
    c.wheel(*PREVIEW_SPOT, 0, dx=RIGHT)


def step_browser_stepped():
    c.check("a tilt over a browser's GIF goes to the next file", c.item_js("browserPreview", "item.name") == "b.mp3",
            str(c.item_js("browserPreview", "item.name")))


def step_browser_audio():
    c.position = c.item_js("browserPreview", "item.player.position")
    c.length = c.item_js("browserPreview", "item.duration")
    c.check("the audio has loaded", c.length > 0, str(c.length))
    c.wheel(*PREVIEW_SPOT, 0, dx=RIGHT)


def step_browser_skipped():
    position = c.item_js("browserPreview", "item.player.position")
    c.check("a tilt over its audio skips, and stays on the file",
            position >= c.position + c.length * 0.08 and c.item_js("browserPreview", "item.name") == "b.mp3",
            f"{c.position} -> {position} of {c.length}")
    c.finish()


c.run(scene, [(1800, step_start), (500, step_forward), (500, step_back), (500, step_not_before_start),
              (500, step_at_start), (700, step_container), (400, step_past_end), (800, step_looped),
              (600, step_browser_stepped), (1000, step_browser_audio), (500, step_browser_skipped)])
