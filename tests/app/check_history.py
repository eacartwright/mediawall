"""
Undo history lasts for the session only (readme section 47): saving
works within the session, nothing is written beside the project, and
reopening starts with no undo.
"""

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
    c.check("saving writes no .history file", not c.history.exists())
    c.check("undo still works after saving", c.sm.property("canUndo"))
    c.sm.undo()
    c.check("undo steps back", objects() == 2)
    c.sm.redo()


def step_reopen():
    c.pc.openPath(str(c.project))                                  # like opening it next time
    c.check("reopened: starts with nothing to undo",
            not c.sm.property("canUndo") and objects() == 3)
    c.finish()


from harness import OUT                                             # noqa: E402
c.project = OUT / "history.mediawall"
c.history = OUT / "history.mediawall.history"
if c.history.exists():
    c.history.unlink()
c.run(Scene(), [(1500, step_edit_and_save), (1000, step_reopen)],
      project_name="history.mediawall")
