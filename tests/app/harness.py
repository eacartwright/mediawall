"""
Shared setup for the app-level checks (tests/app/check_*.py).

Each check script starts the real MediaWall (main.main()) with a project
it builds, runs timed steps against the live window (mouse, keys, wheel,
QML expressions), prints PASS/FAIL lines and a final "N/M passed", and
quits. tests/app/run.py runs them all in separate processes.

These need a display, PySide6, and the sample media in MEDIATEST/
(gitignored). They are slow (seconds each) and are kept apart from the
fast unit tests in tests/, which `python -m unittest` runs.

Settings: MEDIAWALL_SETTINGS is pointed at a scratch .ini file (set by
run.py, or here if missing), so the real settings are never touched.
"""

import os
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_DIR))

MEDIA = APP_DIR / "MEDIATEST"

# Output folder (screenshots, scratch projects): given by run.py, or a
# fresh temp folder when a check is run on its own.
OUT = Path(os.environ.get("MEDIAWALL_CHECK_OUT") or tempfile.mkdtemp(prefix="mediawall-checks-"))
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MEDIAWALL_SETTINGS", str(OUT / "settings.ini"))

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer            # noqa: E402
from PySide6.QtGui import QGuiApplication, QWheelEvent             # noqa: E402
from PySide6.QtQml import QJSValue, QQmlEngine, QQmlExpression     # noqa: E402
from PySide6.QtTest import QTest                                   # noqa: E402

import main as mediawall                                           # noqa: E402
from core.media_browser import MediaBrowser                        # noqa: E402
from core.project import save_project                             # noqa: E402


# ---- Sample media (MEDIATEST/) ----

PHOTO = "IMG_20161015_184258308.jpg"        # 4320 x 2432
SCREENSHOT = "Screenshot 2026-07-20 202445.png"
GIF = "beetlejuice.gif"                     # 600 x 326, animated
VIDEO = "VID_20161226_050020233.mp4"        # phone video, stored sideways
MOV = "IMG_2431.MOV"                        # phone video, stored sideways
WEBM = "steamdeck_thumbstick_move.webm"     # 3 s
AUDIO = "Relaxing ASMR Reiki Healing 2 (3D sound) please wear headphones =).m4a"


def media(name):
    return str(MEDIA / name)


def media_available():
    return all((MEDIA / n).exists() for n in (PHOTO, SCREENSHOT, GIF, VIDEO, MOV, WEBM, AUDIO))


def folder_files(kinds=("image", "video")):
    """MEDIATEST as a browser/browsing container lists it."""
    return [e for e in MediaBrowser().scan_folder(str(MEDIA), True) if e["type"] in kinds]


# ---- Running a check ----

class Check:
    """
    Build a project, start MediaWall on it, and run `steps` one after
    another: each is (delay_ms, function). Access the model as `c.sm`,
    the project controller as `c.pc`, and the window as `c.win`.
    """

    def __init__(self, name):
        self.name = name
        self.results = []
        self.sm = self.pc = self.win = None

    # -- reporting --

    def check(self, label, condition, info=""):
        self.results.append(bool(condition))
        print(("PASS " if condition else "FAIL ") + label + (f"  [{info}]" if info else ""),
              flush=True)

    def finish(self):
        passed = sum(self.results)
        print(f"{passed}/{len(self.results)} passed", flush=True)
        QGuiApplication.quit()

    # -- starting --

    def run(self, scene, steps, project_name=None):
        if not media_available():
            print("SKIP  MEDIATEST sample media not found", flush=True)
            sys.exit(0)

        project = OUT / (project_name or f"{self.name}.mediawall")
        save_project(scene, project)
        sys.argv = [sys.argv[0], str(project)]

        original_open = mediawall.ProjectController.openPath
        started = []

        def open_and_start(controller, path):
            result = original_open(controller, path)
            if not started:
                started.append(True)
                self.sm = controller._model
                self.pc = controller
                self.win = [w for w in QGuiApplication.topLevelWindows()
                            if w.title() and not w.title().endswith("Log")][0]
                # Keyboard shortcuts only reach an active window, so wait
                # (up to ~5 s) for it to become active before starting.
                self.win.requestActivate()
                self._start_when_active(steps, tries=50)
            return result

        mediawall.ProjectController.openPath = open_and_start
        mediawall.main()

    def _start_when_active(self, steps, tries):
        if not self.win.isActive() and tries > 0:
            if tries % 10 == 0:
                self.win.requestActivate()
            QTimer.singleShot(100, lambda: self._start_when_active(steps, tries - 1))
            return
        if not self.win.isActive():
            print("NOTE  window never became active; keyboard checks may fail", flush=True)
        t = 0
        for delay, step in steps:
            t += delay
            QTimer.singleShot(t, step)

    # -- the live app --

    @property
    def scene(self):
        return self.sm.scene

    def js(self, expression):
        """Evaluate a QML expression in Main.qml's context (its ids are visible)."""
        e = QQmlExpression(QQmlEngine.contextForObject(self.win), self.win, expression)
        value, _ = e.evaluate()
        if e.hasError():
            print("JS ERROR:", e.error().toString(), flush=True)
        if isinstance(value, QJSValue):             # arrays, objects -> Python values
            value = value.toVariant()
        return value

    def item_js(self, object_name, expression):
        """
        Evaluate `expression` with `item` = the first visible item with
        this objectName (searched through the whole visual tree, list
        delegates included). Returns None if there's no such item.
        """
        return self.js("""(function() {
            function walk(item) {
                if (item.objectName === %r && item.visible) return item
                for (var i = 0; i < item.children.length; i++) {
                    var hit = walk(item.children[i]); if (hit) return hit
                }
                return null
            }
            // From the root item (the overlay's parent), so popups and
            // dialogs, drawn on the window's overlay, are included.
            var item = walk(window.Overlay.overlay.parent)
            if (!item) return null
            return (%s)
        })()""" % (object_name, expression))

    def center_of(self, object_name):
        """(x, y, width, height): window position of an item's center, and its size."""
        found = self.item_js(object_name, """(function() {
            var p = item.mapToItem(null, item.width / 2, item.height / 2)
            return [p.x, p.y, item.width, item.height] })()""")
        return None if found is None else tuple(float(v) for v in found)

    def grab(self, filename):
        self.win.grabWindow().save(str(OUT / filename))

    # -- input --

    def click(self, x, y, button=Qt.LeftButton, modifiers=Qt.NoModifier):
        QTest.mouseClick(self.win, button, modifiers, QPoint(round(x), round(y)))

    def double_click(self, x, y, button=Qt.LeftButton):
        QTest.mouseDClick(self.win, button, Qt.NoModifier, QPoint(round(x), round(y)))

    def drag(self, start, end, button=Qt.LeftButton, steps=8):
        QTest.mousePress(self.win, button, Qt.NoModifier, QPoint(round(start[0]), round(start[1])))
        for i in range(1, steps + 1):
            QTest.mouseMove(self.win, QPoint(round(start[0] + (end[0] - start[0]) * i / steps),
                                             round(start[1] + (end[1] - start[1]) * i / steps)))
        QTest.mouseRelease(self.win, button, Qt.NoModifier, QPoint(round(end[0]), round(end[1])))

    def move(self, x, y):
        QTest.mouseMove(self.win, QPoint(round(x), round(y)))

    def key(self, key, modifiers=Qt.NoModifier):
        QTest.keyClick(self.win, key, modifiers)

    def wheel(self, x, y, delta, buttons=Qt.NoButton):
        pos = QPointF(x, y)
        QGuiApplication.sendEvent(self.win, QWheelEvent(
            pos, self.win.mapToGlobal(pos), QPoint(), QPoint(0, delta),
            buttons, Qt.NoModifier, Qt.NoScrollPhase, False))

    def open_sidebar(self, tab="layersTab"):
        """Open the right-edge flyout (if closed) and choose a tab."""
        handle = self.center_of("sidebarHandle")
        if handle and handle[0] > self.win.width() - 30:        # closed: tab at the edge
            self.click(handle[0], handle[1])

    def choose_tab(self, tab):
        spot = self.center_of(tab)
        if spot:
            self.click(spot[0], spot[1])


# Re-exported for check scripts.
__all__ = ["Check", "Qt", "OUT", "MEDIA", "media", "folder_files",
           "PHOTO", "SCREENSHOT", "GIF", "VIDEO", "MOV", "WEBM", "AUDIO"]
