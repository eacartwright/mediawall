"""
Phone videos stored sideways (rotation flag) get their upright shape:
new ones on the canvas, in containers, and ones in walls saved before
the fix.
"""

from harness import Check, VIDEO, media
from core.scene import Scene

c = Check("video_size")

scene = Scene()
old = scene.add_source(media(VIDEO), "video", 1920, 1080)          # an older wall's wrong size
placed = scene.add_media(old.id, 700, 100)
placed.width, placed.height = 480, 270
box = scene.add_object("container", 60, 420, width=600, height=300)
scene.add_media_to_container(old.id, box.id)


def step_add():
    c.sm.addMedia(media(VIDEO), "video", 100, 100)


def step_check():
    o = c.scene.get(placed.id)
    c.check("an older wall's sideways video is corrected to portrait, inside its old box",
            o.height > o.width and o.height <= 270 + 0.5, f"{o.width:.0f}x{o.height:.0f}")
    content = c.scene.content_of(box.id)
    c.check("in a container it's re-framed portrait", content.height > content.width)
    new = [m for m in c.scene.objects if m.type == "media" and m.parent_id is None and m.id != placed.id]
    n = new[-1] if new else None
    c.check("a newly placed phone video arrives portrait at the normal width",
            n is not None and abs(n.width - 300) < 1 and n.height > n.width,
            f"{n.width:.0f}x{n.height:.0f}" if n else "none")
    c.finish()


c.run(scene, [(1000, step_add), (3000, step_check)])
