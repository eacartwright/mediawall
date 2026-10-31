"""
The Log window (readme section 37, Log window): Pause holds new lines
back while capture goes on, and Export saves the lines to a text file.
"""

from harness import OUT, Check
from bridge import log_capture
from core.scene import Scene

c = Check("log")

export_path = OUT / "exported-log.txt"
log_capture.QFileDialog.getSaveFileName = staticmethod(
    lambda *args: (str(export_path), ""))


def rows():
    return c.js("appLog.rowCount()")


def log_js(object_name, expression):
    """Like c.item_js, but in the Log window (a window of its own)."""
    return c.js("""(function() {
        function walk(item) {
            if (item.objectName === %r) return item
            for (var i = 0; i < item.children.length; i++) {
                var hit = walk(item.children[i]); if (hit) return hit
            }
            return null
        }
        var item = walk(logWindow.contentItem)
        return item ? (%s) : null
    })()""" % (object_name, expression))


def step_open():
    c.js("logWindow.show()")
    c.js("appLog.clear()")
    print("log check: before pause", flush=True)


def step_pause():
    c.check("a printed line shows in the Log window",
            "log check: before pause" in c.js("appLog.allText()"))
    log_js("logPauseButton", "item.clicked()")
    c.check("Pause pauses", c.js("appLog.paused") is True
            and log_js("logPauseButton", "item.text") == "Resume")
    step_pause.shown = rows()
    for i in range(3):
        print(f"log check: while paused {i}", flush=True)


def step_paused():
    c.check("while paused, new lines aren't shown", rows() == step_pause.shown,
            f"{rows()} rows, {step_pause.shown} before")
    c.check("...they're held back and counted", c.js("appLog.heldCount") >= 3
            and "held back" in log_js("logStatus", "item.text"),
            log_js("logStatus", "item.text"))
    log_js("logExportButton", "item.clicked()")
    text = export_path.read_text(encoding="utf-8") if export_path.exists() else ""
    c.check("Export saves every line, held ones included",
            "before pause" in text and "while paused 2" in text)
    c.check("...and says where", str(export_path) in (log_js("logStatus", "item.text") or ""))
    log_js("logPauseButton", "item.clicked()")


def step_resumed():
    c.check("Resume shows the held lines", not c.js("appLog.paused")
            and c.js("appLog.heldCount") == 0 and rows() >= step_pause.shown + 3
            and log_js("logPauseButton", "item.text") == "Pause")
    c.js("appLog.paused = true")
    c.js("logWindow.close()")
    c.check("closing the window resumes", c.js("appLog.paused") is False)
    c.finish()


c.run(Scene(), [(1000, step_open), (500, step_pause), (500, step_paused), (300, step_resumed)])
