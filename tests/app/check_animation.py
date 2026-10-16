"""
Animated images (readme section 5): double-click starts one over (free,
in a container, and in Present), the Speed submenu's setting reaching
the animation, and the Animated Only filter.
"""

from harness import GIF, MEDIA, PHOTO, Check, Qt, media
from core.media_browser import MediaBrowser
from core.scene import Scene

c = Check("animation")

scene = Scene()
gif = scene.add_source(media(GIF), "image", 600, 326)
photo = scene.add_source(media(PHOTO), "image", 4320, 2432)
free = scene.add_media(gif.id, 420, 100)
free.width, free.height = 300, 163
box = scene.add_object("container", 420, 400, width=300, height=200)
scene.add_media_to_container(gif.id, box.id)


def anim(media_id):
    return f"scene.viewFor('{media_id}').animation"


def content_id():
    return c.scene.content_of(box.id).id


def step_start():
    c.check("the GIF is animated", c.js(anim(free.id) + " !== null"))
    c.sm.setPlaying(free.id, False)


def step_double_click():
    c.check("paused", not c.js(anim(free.id) + ".playing"))
    c.js(anim(free.id) + ".currentFrame = 80")
    c.double_click(570, 180)


def step_restarted():
    c.check("double-click plays it again from the start",
            c.scene.get(free.id).playing and c.js(anim(free.id) + ".playing")
            and c.js(anim(free.id) + ".currentFrame") < 40,
            f"{c.scene.get(free.id).playing} {c.js(anim(free.id) + '.playing')} {c.js(anim(free.id) + '.currentFrame')}")
    c.sm.setSpeed(free.id, 2.0)
    c.check("speed reaches the animation", c.js(anim(free.id) + ".speed") == 2.0)
    c.js(anim(content_id()) + ".currentFrame = 80")
    c.double_click(570, 500)


def step_container():
    c.check("in a container, double-click restarts instead of resetting the view",
            c.js(anim(content_id()) + ".currentFrame") < 40)
    c.click(570, 180, Qt.RightButton)


def step_menu():
    has_speed = c.js("""(function() {
        for (var i = 0; i < objectMenu.count; i++)
            if (objectMenu.itemAt(i).subMenu === objectMenu.speedMenu) return true
        return false })()""")
    c.check("the right-click menu has a Speed submenu showing the speed",
            has_speed and "2×" in c.js("objectMenu.speedMenu.title"), c.js("objectMenu.speedMenu.title"))
    c.js("objectMenu.speedMenu.itemAt(1).triggered()")              # 0.5x
    c.check("choosing a speed sets it", c.scene.get(free.id).speed == 0.5)
    c.js("objectMenu.close()")
    c.win.setProperty("presenting", True)


def step_present():
    c.js(anim(free.id) + ".currentFrame = 80")
    c.double_click(570, 180)


def step_present2():
    c.check("Present: double-click restarts it and stays in Present",
            c.win.property("presenting") and c.js(anim(free.id) + ".currentFrame") < 40)
    names = [e["name"] for e in MediaBrowser().scan_folder(str(MEDIA), True, "animated")]
    c.check("Animated Only lists the GIF and no stills",
            GIF in names and PHOTO not in names, str(names))
    c.finish()


c.run(scene, [(1500, step_start), (500, step_double_click), (400, step_restarted),
              (400, step_container), (600, step_menu), (1200, step_present), (400, step_present2)])
