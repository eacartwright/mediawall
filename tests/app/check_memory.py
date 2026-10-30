"""
Settings > Performance and the Media Memory window: hardware decoding
saved for the next start, the largest still image size, estimates per
loaded media, and hardware decoder failures counted from the log.
"""

import os

from harness import OUT, Check, GIF, PHOTO, VIDEO, media
from bridge.app_settings import AppSettings, apply_hw_decoding
from core.media_cost import HW_ENV
from core.scene import Scene

c = Check("memory")

scene = Scene()
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
gif = scene.add_source(media(GIF), "image")
video = scene.add_source(media(VIDEO), "video")
free_photo = scene.add_media(photo.id, 60, 60)
scene.add_media(gif.id, 500, 60)
scene.add_media(video.id, 60, 400)
box = scene.add_object("container", 600, 400, width=400, height=300)
scene.add_media_to_container(photo.id, box.id)


def rows():
    return c.js("mediaMemory.rows") or []


def photo_rows():
    return [r for r in rows() if r["name"] == PHOTO]


def step_open():
    c.js("settingsDialog.open()")
    c.item_js("settingsTabs", "item.currentIndex = 1")


def step_open2():
    c.check("the image size list shows the setting",
            c.item_js("maxImageSizeBox", "item.displayText") == "Full size")
    c.grab("settings-performance.png")
    x, y, _, _ = c.center_of("openMemoryButton")
    c.click(x, y)
    c.js("settingsDialog.close()")
    # A hardware decoder giving up, as FFmpeg writes it (through the
    # captured output, like the real message).
    print("[h264 @ 0x28517300] Failed setup for format cuda: hwaccel initialisation returned error.",
          flush=True)


def step_window():
    c.check("Open Media Memory opens the window", c.js("memoryWindow.visible") is True)
    places = sorted(r["place"] for r in photo_rows())
    c.check("the photo is listed on the canvas and in its container",
            places == ["canvas", "container"], str(places))
    kinds = {r["name"]: r["kind"] for r in rows()}
    c.check("the GIF counts as animated, the video as a video",
            kinds.get(GIF) == "animated" and kinds.get(VIDEO) == "video", str(kinds))
    full = photo_rows()[0] if photo_rows() else {}
    c.check("the photo is decoded at full size, about 56 MB with mipmaps",
            full.get("size") == "4320 × 2432" and abs(full.get("bytes", 0) - 4320 * 2432 * 4 * 4 / 3) < 2,
            str(full))
    c.check("the second copy shares the first one's texture",
            sorted(r["cost"] for r in photo_rows())[1] == "shared", str([r["cost"] for r in photo_rows()]))
    c.check("biggest first", [r["bytes"] for r in rows()] == sorted((r["bytes"] for r in rows()), reverse=True))
    c.check("the decoder fallback in the log is counted", c.js("mediaMemory.fallbacks") >= 1)
    c.js("memoryWindow").grabWindow().save(str(OUT / "media-memory.png"))
    c.js("appSettings.maxImageSize = 1024")


def step_limited():
    c.js("mediaMemory.refresh()")
    sizes = [r["size"] for r in photo_rows()]
    c.check("limited to 1024 px: the photo is reloaded smaller, in both places",
            sizes == ["1024 × 577", "1024 × 577"] or sizes == ["1024 × 576", "1024 × 576"], str(sizes))
    source = c.scene.sources[photo.id]
    o = c.scene.get(free_photo.id)
    c.check("...while the file's own size and the object's size are unchanged",
            (source.width, source.height) == (4320, 2432) and round(o.width) == round(free_photo.width),
            f"{source.width}x{source.height}")
    c.js("appSettings.maxImageSize = 0")
    c.js("memoryWindow.close()")

    c.js("appSettings.hwDecoding = 'software'")
    c.check("hardware decoding is saved for the next start", AppSettings().hwDecoding == "software")
    saved = os.environ.pop(HW_ENV, None)
    try:
        mode = apply_hw_decoding()
        c.check("...and at the next start turns hardware decoders off",
                mode == ("software", False) and os.environ.get(HW_ENV) == ",", str(mode))
        os.environ[HW_ENV] = "vaapi"
        c.check("a variable set outside the app wins", apply_hw_decoding() == ("vaapi", True))
    finally:
        os.environ.pop(HW_ENV, None)
        if saved is not None:
            os.environ[HW_ENV] = saved
    c.js("appSettings.hwDecoding = 'auto'")


def step_restored():
    c.js("mediaMemory.refresh()")
    c.check("back to full size", [r["size"] for r in photo_rows()] == ["4320 × 2432"] * 2)
    c.finish()


c.run(scene, [(1500, step_open), (500, step_open2), (3000, step_window), (2500, step_limited),
              (2500, step_restored)])
