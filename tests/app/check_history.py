"""
Undo history kept between sessions (readme section 47): save, reopen
and undo, and a project changed elsewhere ignoring stale history.
"""

import json

from harness import Check

from core.scene import Scene

c = Check("history")


def objects():
    return len(c.scene.objects)


def step_edit_and_save():
    c.sm.addContainer(10, 10)
    c.sm.addBrowser(300, 10)
    c.sm.addContainer(600, 10)
    c.pc.save()
    c.check("saving writes the .history file", c.history.exists())


def step_reopen():
    c.pc.openPath(str(c.project))                                  # like opening it next time
    c.check("reopened: undo is available", c.sm.property("canUndo") and objects() == 3)
    counts = []
    while c.sm.property("canUndo"):
        c.sm.undo()
        counts.append(objects())
    c.check("undo walks back through last session's changes", counts == [2, 1, 0], str(counts))
    c.sm.redo()
    c.check("redo works too", objects() == 1)


def step_stale():
    c.pc.openPath(str(c.project))
    data = json.loads(c.project.read_text(encoding="utf-8"))
    data["objects"][0]["x"] += 5                                    # edited behind MediaWall's back
    c.project.write_text(json.dumps(data), encoding="utf-8")
    c.pc.openPath(str(c.project))
    c.check("a project changed since: its stale history is ignored", not c.sm.property("canUndo"))
    c.finish()


from harness import OUT                                             # noqa: E402
c.project = OUT / "history.mediawall"
c.history = OUT / "history.mediawall.history"
if c.history.exists():
    c.history.unlink()
c.run(Scene(), [(1500, step_edit_and_save), (1000, step_reopen), (1000, step_stale)],
      project_name="history.mediawall")
